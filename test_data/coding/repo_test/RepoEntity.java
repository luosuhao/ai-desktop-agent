import java.math.BigDecimal;

/**
 * 银行间回购反向实体类
 */
public class RepoEntity {
    private String id;
    private String nowDay;
    private String fundCode;
    private String fundName;
    private String riskMsg;
    private String demandRate;
    private BigDecimal minRepoRate;
    private String purpose;
    private String isDelete;
    private String createBy;
    private String isApproval;
    private String tradeAmount;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getNowDay() { return nowDay; }
    public void setNowDay(String nowDay) { this.nowDay = nowDay; }

    public String getFundCode() { return fundCode; }
    public void setFundCode(String fundCode) { this.fundCode = fundCode; }

    public String getFundName() { return fundName; }
    public void setFundName(String fundName) { this.fundName = fundName; }

    public String getRiskMsg() { return riskMsg; }
    public void setRiskMsg(String riskMsg) { this.riskMsg = riskMsg; }

    public String getDemandRate() { return demandRate; }
    public void setDemandRate(String demandRate) { this.demandRate = demandRate; }

    public BigDecimal getMinRepoRate() { return minRepoRate; }
    public void setMinRepoRate(BigDecimal minRepoRate) { this.minRepoRate = minRepoRate; }

    public String getPurpose() { return purpose; }
    public void setPurpose(String purpose) { this.purpose = purpose; }

    public String getIsDelete() { return isDelete; }
    public void setIsDelete(String isDelete) { this.isDelete = isDelete; }

    public String getCreateBy() { return createBy; }
    public void setCreateBy(String createBy) { this.createBy = createBy; }

    public String getIsApproval() { return isApproval; }
    public void setIsApproval(String isApproval) { this.isApproval = isApproval; }

    public String getTradeAmount() { return tradeAmount; }
    public void setTradeAmount(String tradeAmount) { this.tradeAmount = tradeAmount; }

    // ============ extra fields for Bug testing ============
    private java.util.Date createTime;
    private String updateBy;

    public java.util.Date getCreateTime() { return createTime; }
    public void setCreateTime(java.util.Date createTime) { this.createTime = createTime; }
    public String getUpdateBy() { return updateBy; }
    public void setUpdateBy(String updateBy) { this.updateBy = updateBy; }
}
