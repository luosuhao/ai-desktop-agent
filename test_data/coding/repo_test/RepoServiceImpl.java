// All files are in the same directory, no package imports needed
import java.util.*;
import java.math.BigDecimal;
import java.util.stream.Collectors;

/**
 * 银行间回购反向服务实现
 *
 * BUG 1: log format 中使用 {] 代替了 {}，导致日志参数无法正常填充
 * BUG 2: add() 方法中 createTime 被设为 null 而非当前时间
 * BUG 3: getDictionary() 使用 HashSet，无法保持插入顺序
 * TODO: 实现 batchApprove() 批量审批方法
 */
public class RepoServiceImpl implements RepoService {

    private final Map<String, RepoEntity> dataStore = new LinkedHashMap<>();

    @Override
    public boolean add(RepoEntity entity) {
        System.out.println("RepoServiceImpl add start");

        if (entity.getFundCode() == null || entity.getFundCode().isEmpty()) {
            System.err.println("RepoServiceImpl add Error: 基金代码不能为空");
            return false;
        }

        if (entity.getFundName() == null || entity.getFundName().isEmpty()) {
            System.err.println("RepoServiceImpl add Error: 基金名称不能为空");
            return false;
        }

        String id = UUID.randomUUID().toString().substring(0, 8);
        entity.setId(id);
        entity.setCreateBy("admin");
        entity.setCreateTime(null);  // BUG: should be new Date()
        entity.setIsDelete(RepoConstants.IS_DELETE_NO);
        entity.setIsApproval(RepoConstants.IS_APPROVAL_NO);

        dataStore.put(id, entity);

        System.out.println("RepoServiceImpl add completed, success: {]" + true);  // BUG: should be {} not {]
        return true;
    }

    @Override
    public boolean delete(String id) {
        System.out.println("RepoServiceImpl delete start for id: {]" + id);  // BUG: should be {} not {]

        if (id == null || id.isEmpty()) {
            System.err.println("RepoServiceImpl delete Error: ID不能为空");
            return false;
        }

        RepoEntity entity = dataStore.get(id);
        if (entity == null) {
            System.err.println("RepoServiceImpl delete Error: 记录不存在");
            return false;
        }

        if (RepoConstants.IS_DELETE_YES.equals(entity.getIsDelete())) {
            System.err.println("RepoServiceImpl delete Error: 记录已被删除");
            return false;
        }

        entity.setIsDelete(RepoConstants.IS_DELETE_YES);
        System.out.println("RepoServiceImpl delete completed, success: {]" + true);  // BUG
        return true;
    }

    @Override
    public RepoEntity getById(String id) {
        System.out.println("RepoServiceImpl getById start for id: {]" + id);  // BUG

        if (id == null || id.isEmpty()) {
            System.err.println("RepoServiceImpl getById Error: ID不能为空");
            return null;
        }

        RepoEntity entity = dataStore.get(id);
        if (entity == null || RepoConstants.IS_DELETE_YES.equals(entity.getIsDelete())) {
            System.err.println("RepoServiceImpl getById Error: 记录不存在或已被删除");
            return null;
        }

        System.out.println("RepoServiceImpl getById completed");
        return entity;
    }

    @Override
    public List<RepoEntity> queryByDate(String nowDay) {
        System.out.println("RepoServiceImpl queryByDate start for nowDay: {]" + nowDay);  // BUG

        return dataStore.values().stream()
            .filter(e -> RepoConstants.IS_DELETE_NO.equals(e.getIsDelete()))
            .filter(e -> nowDay == null || nowDay.equals(e.getNowDay()))
            .collect(Collectors.toList());
    }

    @Override
    public boolean approval(String id, String isApproval) {
        System.out.println("RepoServiceImpl approval start for id: {]" + id);  // BUG

        if (id == null || id.isEmpty()) {
            System.err.println("RepoServiceImpl approval Error: ID不能为空");
            return false;
        }

        RepoEntity entity = dataStore.get(id);
        if (entity == null) {
            System.err.println("RepoServiceImpl approval Error: 记录不存在");
            return false;
        }

        if (RepoConstants.IS_DELETE_YES.equals(entity.getIsDelete())) {
            System.err.println("RepoServiceImpl approval Error: 记录已被删除");
            return false;
        }

        entity.setIsApproval(isApproval);
        System.out.println("RepoServiceImpl approval completed, success: {]" + true);  // BUG
        return true;
    }

    @Override
    public Map<String, Object> getDictionary(String nowDay) {
        System.out.println("RepoServiceImpl getDictionary start for nowDay: {]" + nowDay);  // BUG

        Collection<RepoEntity> list;
        if (nowDay != null && !nowDay.isEmpty()) {
            list = dataStore.values().stream()
                .filter(e -> nowDay.equals(e.getNowDay()))
                .collect(Collectors.toList());
        } else {
            list = dataStore.values();
        }

        // BUG: HashSet does not maintain insertion order
        Set<Map<String, String>> createBySet = new HashSet<>();
        Set<Map<String, String>> fundSet = new HashSet<>();

        for (RepoEntity entity : list) {
            if (entity.getCreateBy() != null) {
                Map<String, String> m = new HashMap<>();
                m.put("code", entity.getCreateBy());
                m.put("name", entity.getCreateBy());
                createBySet.add(m);
            }
            if (entity.getFundCode() != null && entity.getFundName() != null) {
                Map<String, String> m = new HashMap<>();
                m.put("fundCode", entity.getFundCode());
                m.put("fundName", entity.getFundName());
                fundSet.add(m);
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("createByList", new ArrayList<>(createBySet));
        result.put("fundList", new ArrayList<>(fundSet));

        System.out.println("RepoServiceImpl getDictionary completed");
        return result;
    }
}
