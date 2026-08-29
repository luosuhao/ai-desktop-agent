"""金融计算问答：RAG 检索表格数据 + LLM 通过服务器安全计算器得到精确结果。"""
import ast
import json
import math

MAX_ROUNDS = 3
MAX_TABLES = 10
TABLE_LINES_CAP = 60
TABLE_CHARS_CAP = 4000


# ---------- 计算器工具 ----------

CALCULATE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "安全地计算一个金融算术表达式。只能基于上下文中表格的数字，使用纯算术运算符 + - * / ( ) 及数学函数（sqrt/abs/round/min/max/log 等）。表达式不得包含百分号、货币符号、逗号或单位文字；百分比请显式乘以或除以 100。",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "算术表达式，例如 '(885.7-661.8)/661.8*100'"
                },
                "label": {
                    "type": "string",
                    "description": "该计算含义的中文标签，例如 '营业收入同比增长率(%)'"
                }
            },
            "required": ["expression", "label"]
        }
    }
}

FINANCE_SYSTEM_PROMPT = """你是财务报表分析助手。基于提供的表格与文档数据，精确回答金融计算类问题。

规则：
1. 所有数字必须来自上下文中的表格数据，不得编造；数据不足时明确回答"数据不足"，并列出缺失的字段。
2. 凡需要计算的答案（增长率、毛利率、同比、占比、均值、合计等）必须先调用 calculate 工具获得精确结果，禁止心算或直接口算。
3. calculate 的 expression 只能包含数字、小数点和运算符 + - * / ( ) 以及数学函数 sqrt/abs/round/min/max/log/log10/exp/floor/ceil 等；不要写百分号、货币符号、逗号、单位或中文文字。百分比请显式乘以或除以 100。
4. 每次调用 calculate 必须给 label，用中文注明该计算的含义与单位（如"营业收入同比增长率(%)"）。
5. 最终回答要引用上下文中的精确数字，并用一行说明计算方式，例如：毛利率 = 毛利润 / 营业收入 × 100% = 261.2 / 885.7 × 100% ≈ 29.5%。
6. 金额类数字需结合列头或表注中的单位理解（如"单位：亿元"），并在 label 与回答中注明单位。
7. 涉及时期（年份/季度/月份）的问题要明确回答对应时期。
8. 用中文回答。"""


# ---------- 安全求值器 ----------

_ALLOWED_NODES = (
    ast.Expression, ast.Constant, ast.BinOp, ast.UnaryOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Call, ast.Name, ast.Load,
)

_ALLOWED_FUNCS = {
    "abs": abs, "round": round, "sqrt": math.sqrt, "floor": math.floor,
    "ceil": math.ceil, "log": math.log, "log10": math.log10,
    "exp": math.exp, "min": min, "max": max,
}

_ALLOWED_CONSTS = {"pi": math.pi, "e": math.e}

_MAX_EXPR_LEN = 500
_MAX_POW_EXP = 1000
_MAX_RESULT = 1e15


def _reject_huge_pow(node: ast.AST):
    """递归检查 Pow 的指数，拒绝超大幂运算防 DoS。"""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
        if isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float)):
            if abs(node.right.value) > _MAX_POW_EXP:
                raise ValueError("exponent too large")
        if isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Pow):
            _reject_huge_pow(node.left)
        if isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Pow):
            _reject_huge_pow(node.right)


def safe_eval(expr: str) -> dict:
    """白名单 ast 求值。返回 {'expression','result'} 或 {'error'}。"""
    if not isinstance(expr, str) or not expr.strip():
        return {"error": "empty expression"}
    if len(expr) > _MAX_EXPR_LEN:
        return {"error": "expression too long"}
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return {"error": f"invalid expression: {e}"}

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return {"error": f"unsupported construct: {type(node).__name__}"}
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_FUNCS and node.id not in _ALLOWED_CONSTS:
            return {"error": f"unknown name: {node.id}"}
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            try:
                _reject_huge_pow(node)
            except ValueError as e:
                return {"error": str(e)}

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in _ALLOWED_CONSTS:
                return _ALLOWED_CONSTS[node.id]
            return _ALLOWED_FUNCS[node.id]
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.Pow):
                return left ** right
            raise ValueError("unsupported operator")
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            raise ValueError("unsupported operator")
        if isinstance(node, ast.Call):
            fn = _ALLOWED_FUNCS.get(node.func.id)
            if fn is None:
                raise ValueError("unknown function")
            return fn(*[_eval(a) for a in node.args])
        raise ValueError(f"unsupported node: {type(node).__name__}")

    try:
        value = _eval(tree.body)
        if isinstance(value, bool):
            value = float(value)
        if isinstance(value, (int, float)):
            if abs(value) > _MAX_RESULT:
                return {"error": "result out of range"}
            return {"expression": expr, "result": round(value, 8)}
        return {"error": f"non-numeric result: {type(value).__name__}"}
    except ZeroDivisionError:
        return {"error": "division by zero"}
    except Exception as e:
        return {"error": f"evaluation failed: {e}"}


# ---------- 上下文构造 ----------

def _truncate_markdown(md: str) -> str:
    lines = md.splitlines()
    if len(lines) > TABLE_LINES_CAP:
        lines = lines[:TABLE_LINES_CAP]
        lines.append("...(表格过长已截断)")
    return "\n".join(lines)[:TABLE_CHARS_CAP]


# ---------- 编排 ----------

def finance_qa(data: dict, vector_store, model_adapter) -> dict:
    q = (data.get("query") or "").strip()
    doc_ids = data.get("document_ids") or None
    top_k = int(data.get("top_k") or 8)
    max_tables = int(data.get("max_tables") or MAX_TABLES)

    search = vector_store.search(q, top_k, "hybrid", True, document_ids=doc_ids)
    hits = search.get("results", [])

    context_parts = []
    evidence = []
    table_sources = []
    seen_ids = set()

    for r in hits:
        cid = r.get("chunk_id")
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        ctx = f"[{r.get('chunk_type', 'text')}] 来源: {r.get('document_name', '')}"
        if r.get("page_number"):
            ctx += f" 第{r['page_number']}页"
        ctx += "\n" + r["content"]
        context_parts.append(ctx)
        evidence.append(r)

    # 选中文档时直接注入全部表格块，不依赖 embedding 召回数字表
    if doc_ids:
        table_chunks = vector_store.get_document_chunks(doc_ids, chunk_type="table")
        injected = 0
        for chunk in table_chunks:
            if injected >= max_tables:
                break
            content = chunk.get("content", "")
            if not content:
                continue
            cid = chunk.get("id")
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            meta = chunk.get("metadata", {})
            page = chunk.get("page_number")
            ctx = f"[table] 来源: {meta.get('filename', '')}"
            if page:
                ctx += f" 第{page}页"
            ctx += "\n" + _truncate_markdown(content)
            context_parts.append(ctx)
            table_sources.append({
                "document_id": meta.get("document_id", ""),
                "document_name": meta.get("filename", ""),
                "page_number": page,
                "rows": meta.get("rows"),
                "cols": meta.get("cols"),
                "table_source": meta.get("table_source", ""),
            })
            injected += 1

    context = "\n\n".join(context_parts)

    messages = [
        {"role": "system", "content": FINANCE_SYSTEM_PROMPT},
        {"role": "user", "content":
            f"Context:\n{context}\n\nQuestion: {q}\n\n"
            "Answer based on the context. Use the calculate tool for any computation."},
    ]

    steps = []
    final_content = ""
    for _ in range(MAX_ROUNDS):
        resp = model_adapter.chat(messages, [CALCULATE_TOOL_SCHEMA])
        content = resp.get("content") or ""
        tool_calls = resp.get("tool_calls") or []

        assistant_msg = {"role": "assistant"}
        if content:
            assistant_msg["content"] = content
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["function"]["name"],
                              "arguments": tc["function"]["arguments"]}}
                for tc in tool_calls
            ]
            if "content" not in assistant_msg:
                assistant_msg["content"] = None
        messages.append(assistant_msg)

        if not tool_calls:
            final_content = content
            break

        for tc in tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            expr = args.get("expression", "")
            label = args.get("label", "")
            calc = safe_eval(expr)
            if "result" in calc:
                tool_result = json.dumps({"result": calc["result"]}, ensure_ascii=False)
                steps.append({
                    "tool": "calculate", "label": label or "",
                    "expression": expr, "result": str(calc["result"]),
                })
            else:
                tool_result = json.dumps(calc, ensure_ascii=False)
                steps.append({
                    "tool": "calculate", "label": label or "",
                    "expression": expr,
                    "result": "ERROR: " + calc.get("error", ""),
                })
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
    else:
        # 循环耗尽仍未给出最终文字答案
        final_content = ""

    if not final_content.strip() and steps:
        lines = ["（模型未生成完整说明，以下为计算过程摘要）"]
        for s in steps:
            lines.append(f"- {s['label']}: {s['expression']} = {s['result']}")
        final_content = "\n".join(lines)

    return {
        "query": q,
        "answer": final_content,
        "evidence": evidence,
        "table_sources": table_sources,
        "calculation_steps": steps,
        "total_evidence": len(evidence),
    }
