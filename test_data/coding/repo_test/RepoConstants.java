/**
 * 银行间回购反向业务常量类
 */
public final class RepoConstants {

    private RepoConstants() {}

    // ==================== 删除标志 ====================
    public static final String IS_DELETE_YES = "1";
    public static final String IS_DELETE_NO = "0";

    // ==================== 审批标志 ====================
    public static final String IS_APPROVAL_YES = "1";
    public static final String IS_APPROVAL_NO = "0";

    // ==================== 业务类型 ====================
    public static final String BIZ_TYPE_REPO = "正回购";

    // ==================== 数据库字段名 ====================
    public static final String COL_IS_DELETE = "IS_DELETE";
    public static final String COL_IS_APPROVAL = "IS_APPROVAL";
    public static final String COL_NOW_DAY = "NOW_DAY";
    public static final String COL_CREATE_TIME = "CREATE_TIME";
}
