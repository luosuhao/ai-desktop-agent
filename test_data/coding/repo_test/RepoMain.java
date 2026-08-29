// All files are in the same directory, no package imports needed
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * Repo Test Runner - 用于测试 Coding Agent 功能
 *
 * 测试场景：
 * 1. 修复 log 格式中 {] 应为 {} 的 Bug（涉及 RepoServiceImpl.java 中多处）
 * 2. 修复 add() 方法中 createTime 被设为 null 的 Bug
 * 3. 修复 getDictionary() 使用 HashSet 不保持插入顺序的 Bug
 * 4. 实现 batchApprove() 批量审批方法
 * 5. 运行此 Main 类验证所有修改
 */
public class RepoMain {
    public static void main(String[] args) {
        RepoService service = new RepoServiceImpl();
        System.out.println("============================================");
        System.out.println(" Repo Test - Coding Agent 功能测试");
        System.out.println("============================================");

        // 1. 测试新增
        System.out.println("\n--- 测试: add() ---");
        RepoEntity entity1 = new RepoEntity();
        entity1.setFundCode("GF-001");
        entity1.setFundName("广发基金");
        entity1.setNowDay("2026-07-29");
        entity1.setTradeAmount("50000000");
        System.out.println("新增结果: " + service.add(entity1));

        RepoEntity entity2 = new RepoEntity();
        entity2.setFundCode("ZH-002");
        entity2.setFundName("招商基金");
        entity2.setNowDay("2026-07-29");
        entity2.setTradeAmount("30000000");
        System.out.println("新增结果: " + service.add(entity2));

        RepoEntity entity3 = new RepoEntity();
        entity3.setFundCode("HT-003");
        entity3.setFundName("华泰基金");
        entity3.setNowDay("2026-07-28");
        entity3.setTradeAmount("20000000");
        System.out.println("新增结果: " + service.add(entity3));

        // 2. 测试查询
        System.out.println("\n--- 测试: queryByDate() ---");
        List<RepoEntity> list = service.queryByDate("2026-07-29");
        System.out.println("2026-07-29 的记录数: " + list.size());  // 应为 2

        // 3. 测试审批
        System.out.println("\n--- 测试: approval() ---");
        String id = entity1.getId();
        if (id != null) {
            System.out.println("审批结果: " + service.approval(id, RepoConstants.IS_APPROVAL_YES));
        }

        // 4. 测试字典
        System.out.println("\n--- 测试: getDictionary() ---");
        Map<String, Object> dict = service.getDictionary(null);
        System.out.println("创建人列表: " + dict.get("createByList"));
        System.out.println("基金列表: " + dict.get("fundList"));

        // 5. 测试获取
        System.out.println("\n--- 测试: getById() ---");
        if (id != null) {
            RepoEntity found = service.getById(id);
            System.out.println("查询结果: " + (found != null ? found.getFundName() : "null"));
        }

        // 6. 测试删除
        System.out.println("\n--- 测试: delete() ---");
        if (id != null) {
            System.out.println("删除结果: " + service.delete(id));
            RepoEntity afterDelete = service.getById(id);
            System.out.println("删除后查询: " + (afterDelete == null ? "已删除(正确)" : "仍存在"));
        }

        // 7. 测试空参数
        System.out.println("\n--- 测试: 空参数处理 ---");
        System.out.println("空ID查询: " + (service.getById("") == null ? "返回null(正确)" : "非null"));
        System.out.println("空ID删除: " + service.delete(""));

        System.out.println("\n============================================");
        System.out.println(" 测试完成");
        System.out.println("============================================");
    }
}
