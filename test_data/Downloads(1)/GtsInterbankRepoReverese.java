package com.gtfund.cloud.gts.admin.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Date;
import lombok.Data;

/**
 * 银行间回购反向
 * @TableName GTS_INTERBANK_REPO_REVERESE
 */
@TableName(value ="GTS_INTERBANK_REPO_REVERESE")
@Data
public class GtsInterbankRepoReverese implements Serializable {
    /**
     * 
     */
    @TableId(value = "ID", type = IdType.ASSIGN_ID)
    private String id;

    /**
     *
     */
    @TableField(value = "NOW_DAY")
    private String nowDay;

    /**
     * 基金代码
     */
    @TableField(value = "FUND_CODE")
    private String fundCode;

    /**
     * 基金名称
     */
    @TableField(value = "FUND_NAME")
    private String fundName;

    /**
     * 风控信息
     */
    @TableField(value = "RISK_MSG")
    private String riskMsg;

    /**
     * 指令序号
     */
    @TableField(value = "DAILY_INSTRUCTION_NO")
    private String dailyInstructionNo;

    /**
     * 趴账活期利率
     */
    @TableField(value = "DEMAND_RATE")
    private String demandRate;

    /**
     * 同期限最低逆回购利率
     */
    @TableField(value = "MIN_REPO_RATE")
    private BigDecimal minRepoRate;

    /**
     * 资金反向用途：趴账/日内套利
     */
    @TableField(value = "PURPOSE")
    private String purpose;

    /**
     * 已删除1；未删除0
     */
    @TableField(value = "IS_DELETE")
    private String isDelete;

    /**
     *
     */
    @TableField(value = "CREATE_TIME")
    private Date createTime;

    /**
     *
     */
    @TableField(value = "CREATE_BY")
    private String createBy;

    /**
     *
     */
    @TableField(value = "UPDATE_TIME")
    private Date updateTime;

    /**
     *
     */
    @TableField(value = "UPDATE_BY")
    private String updateBy;

    /**
     * 业务类型：正回购；
     */
    @TableField(value = "BIZ_TYPE")
    private String bizType;

    /**
     * 交易金额（亿）
     */
    @TableField(value = "TRADE_AMOUNT")
    private String tradeAmount;

    /**
     * 已审批1；未审批0
     */
    @TableField(value = "IS_APPROVAL")
    private String isApproval;

	@TableField(exist = false)
	private String repoElementsId;

    @TableField(exist = false)
    private static final long serialVersionUID = 1L;
}