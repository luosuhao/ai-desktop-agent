# Repo Test - Coding Agent 功能测试

本目录包含从公司实际项目简化的银行间回购反向管理代码，用于测试 Coding Agent 功能。

## 文件结构

```
repo_test/
├── RepoEntity.java            # 实体类（含 getter/setter）
├── RepoService.java           # 服务接口（含 TODO）
├── RepoServiceImpl.java       # 服务实现（含 3 个 Bug）
├── RepoConstants.java         # 常量类
├── RepoMain.java              # 测试运行器
└── README.md                  # 本文件
```

## Bug 清单

| 编号 | 文件 | 行号 | Bug 描述 | 类型 |
|------|------|------|----------|------|
| 1 | RepoServiceImpl.java | 多处 | log 格式中使用 `{]` 代替了 `{}`，导致参数无法正常填充 | 格式错误 |
| 2 | RepoServiceImpl.java | add() 方法 | `createTime` 被设为 `null` 而非当前时间（`new Date()`） | 逻辑错误 |
| 3 | RepoServiceImpl.java | getDictionary() | 使用 `HashSet` 而非 `LinkedHashSet`，无法保持插入顺序 | 顺序错误 |

## TODO 清单

| 编号 | 位置 | 描述 |
|------|------|------|
| 1 | RepoService.java | 添加 `batchApprove(List<String> ids, String isApproval)` 方法 |
| 2 | RepoServiceImpl.java | 实现 `batchApprove()` 方法，返回成功审批的记录数 |

## 推荐测试任务

| 任务描述 | 测试目标 |
|----------|----------|
| "修复 RepoServiceImpl.java 中 log 格式的 Bug" | Java 字符串格式修复 |
| "修复 RepoServiceImpl.java 中 createTime 设为 null 的 Bug" | Java 逻辑修复 |
| "修复 RepoServiceImpl.java 中 HashSet 导致顺序问题的 Bug" | Java 集合类型修复 |
| "修复 RepoServiceImpl.java 中的所有 Bug" | 多 Bug 综合修复 |
| "实现 batchApprove 批量审批方法" | Java 代码生成 + 编译运行 |
| "修复所有 Bug 并实现 batchApprove，然后运行 RepoMain 验证" | 端到端测试 |

## 运行方式

```bash
# 编译（使用 UTF-8 编码）
cd test_data/coding/repo_test
javac -encoding utf-8 RepoMain.java

# 运行
java RepoMain
```
