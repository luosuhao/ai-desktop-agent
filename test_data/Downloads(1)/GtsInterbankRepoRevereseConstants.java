package com.gtfund.cloud.gts.admin.entity;

/**
 * 银行间回购反向业务常量类
 * 统一封装 GtsInterbankRepoReverese 中所有硬编码状态字符串，消除魔术值
 */
public final class GtsInterbankRepoRevereseConstants {

    private GtsInterbankRepoRevereseConstants() {
        // 工具类，禁止实例化
    }

    // ==================== 删除标志 ====================
    /** 已删除 */
    public static final String IS_DELETE_YES = "1";
    /** 未删除 */
    public static final String IS_DELETE_NO = "0";

    // ==================== 审批标志 ====================
    /** 已审批 */
    public static final String IS_APPROVAL_YES = "1";
    /** 未审批 */
    public static final String IS_APPROVAL_NO = "0";

    // ==================== 业务类型 ====================
    /** 正回购 */
    public static final String BIZ_TYPE_REPO = "正回购";

    // ==================== 数据库字段名 ====================
    /** 数据库字段：IS_DELETE */
    public static final String COL_IS_DELETE = "IS_DELETE";
    /** 数据库字段：IS_APPROVAL */
    public static final String COL_IS_APPROVAL = "IS_APPROVAL";
    /** 数据库字段：NOW_DAY */
    public static final String COL_NOW_DAY = "NOW_DAY";
    /** 数据库字段：CREATE_TIME */
    public static final String COL_CREATE_TIME = "CREATE_TIME";
}
