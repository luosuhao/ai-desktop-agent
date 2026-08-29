package com.gtfund.cloud.gts.admin.controller.repo;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.gtfund.cloud.common.core.util.R;
import com.gtfund.cloud.gts.admin.entity.GtsInterbankRepoReverese;
import com.gtfund.cloud.gts.admin.service.GtsInterbankRepoRevereseService;
import com.gtfund.cloud.gts.admin.service.repo.ReverseRepoService;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.Map;
import java.util.regex.Pattern;

@Slf4j
@RestController
@RequestMapping("/gts-interbank-repo-reverese")
@Api(value = "GtsInterbankRepoRevereseController", tags = "银行间回购反向管理")
public class GtsInterbankRepoRevereseController {

    @Autowired
    private GtsInterbankRepoRevereseService gtsInterbankRepoRevereseService;

    @Autowired
    private ReverseRepoService reverseRepoService;

    @ApiOperation(value = "新增银行间回购反向记录")
    @PostMapping("/add")
    @Transactional(rollbackFor = Exception.class)
    public R add(@RequestBody GtsInterbankRepoReverese entity) {
        log.info("GtsInterbankRepoRevereseController add start");
        try {
            boolean success = gtsInterbankRepoRevereseService.add(entity);
            log.info("GtsInterbankRepoRevereseController add completed, success: {}", success);
            if (success) {
                return R.ok("新增成功！");
            } else {
                return R.failed("新增失败！");
            }
        } catch (IllegalArgumentException e) {
            log.error("GtsInterbankRepoRevereseController add Error occurred", e);
            return R.failed("新增失败：" + e.getMessage());
        } catch (Exception e) {
            log.error("GtsInterbankRepoRevereseController add Error occurred", e);
            return R.failed("新增失败：" + e.getMessage());
        }
    }

    @ApiOperation(value = "删除银行间回购反向记录（软删除）")
    @GetMapping("/delete")
    @Transactional(rollbackFor = Exception.class)
    public R delete(@RequestParam String id, @RequestParam(required = false) String repoElementsId) {
        log.info("GtsInterbankRepoRevereseController delete start for id: {}, repoElementsId :{}", id, repoElementsId);
        try {
            boolean success = gtsInterbankRepoRevereseService.delete(id, repoElementsId);
            log.info("GtsInterbankRepoRevereseController delete completed, success: {}", success);
            if (success) {
                return R.ok("删除成功！");
            } else {
                return R.failed("删除失败！");
            }
        } catch (IllegalArgumentException e) {
            log.error("GtsInterbankRepoRevereseController delete Error occurred", e);
            return R.failed("删除失败：" + e.getMessage());
        } catch (Exception e) {
            log.error("GtsInterbankRepoRevereseController delete Error occurred", e);
            return R.failed("删除失败：" + e.getMessage());
        }
    }

	@ApiOperation(value = "审批银行间回购反向记录")
	@GetMapping("/approval")
	@Transactional(rollbackFor = Exception.class)
	public R approval(@RequestParam String id, @RequestParam String isApproval) {
		log.info("GtsInterbankRepoRevereseController approval start for id: {}", id);
		try {
			boolean success = gtsInterbankRepoRevereseService.approval(id, isApproval);
			log.info("GtsInterbankRepoRevereseController approval completed, success: {}", success);
			if (success) {
				return R.ok("审批成功！");
			} else {
				return R.failed("审批失败！");
			}
		} catch (IllegalArgumentException e) {
			log.error("GtsInterbankRepoRevereseController approval Error occurred", e);
			return R.failed("审批失败：" + e.getMessage());
		} catch (Exception e) {
			log.error("GtsInterbankRepoRevereseController approval Error occurred", e);
			return R.failed("审批失败：" + e.getMessage());
		}
	}

    @ApiOperation(value = "按日期分页查询银行间回购反向记录")
    @GetMapping("/list")
    public R list(Page<GtsInterbankRepoReverese> page,
                  @RequestParam(required = false) String nowDay) {
        log.info("GtsInterbankRepoRevereseController list start for nowDay: {}", nowDay);
        try {
            IPage<GtsInterbankRepoReverese> resultPage = gtsInterbankRepoRevereseService.queryByDate(page, nowDay);
            log.info("GtsInterbankRepoRevereseController list completed");
            return R.ok(resultPage);
        } catch (Exception e) {
            log.error("GtsInterbankRepoRevereseController list Error occurred", e);
            return R.failed("查询失败：" + e.getMessage());
        }
    }

    @ApiOperation(value = "根据ID查询银行间回购反向记录")
    @GetMapping("/get/{id}")
    public R getById(@PathVariable String id) {
        log.info("GtsInterbankRepoRevereseController getById start for id: {}", id);
        try {
            GtsInterbankRepoReverese entity = gtsInterbankRepoRevereseService.getByIdWithCheck(id);
            log.info("GtsInterbankRepoRevereseController getById completed");
            return R.ok(entity);
        } catch (IllegalArgumentException e) {
            log.error("GtsInterbankRepoRevereseController getById Error occurred", e);
            return R.failed("查询失败：" + e.getMessage());
        } catch (Exception e) {
            log.error("GtsInterbankRepoRevereseController getById Error occurred", e);
            return R.failed("查询失败：" + e.getMessage());
        }
    }

    @ApiOperation(value = "获取字典数据（createBy、fundCode/fundName）")
    @GetMapping("/dict")
    public R getDictionary(@RequestParam(required = false) String nowDay) {
        log.info("GtsInterbankRepoRevereseController getDictionary start for nowDay: {}", nowDay);
        try {
            if (StringUtils.isNotBlank(nowDay)) {
                String datePattern = "^\\d{4}-\\d{2}-\\d{2}$";
                if (!Pattern.matches(datePattern, nowDay)) {
                    log.error("GtsInterbankRepoRevereseController getDictionary Error occurred: 日期格式不正确，应为YYYY-MM-DD");
                    return R.failed("日期格式不正确，应为YYYY-MM-DD");
                }
            }
            
            Map<String, Object> dictionary = gtsInterbankRepoRevereseService.getDictionary(nowDay);
            log.info("GtsInterbankRepoRevereseController getDictionary completed");
            return R.ok(dictionary);
        } catch (Exception e) {
            log.error("GtsInterbankRepoRevereseController getDictionary Error occurred", e);
            return R.failed("获取字典数据失败：" + e.getMessage());
        }
    }

    @ApiOperation(value = "根据期限查询当日最小利率")
    @GetMapping("/min-en-rate")
    public R getMinEnRateByHgDays(@RequestParam Integer hgDays, 
                                   @RequestParam(required = false) String nowdate) {
        log.info("GtsInterbankRepoRevereseController getMinEnRateByHgDays start for hgDays: {}, nowdate: {}", hgDays, nowdate);
        try {
            
            if (StringUtils.isNotBlank(nowdate)) {
                String datePattern = "^\\d{4}-\\d{2}-\\d{2}$";
                if (!Pattern.matches(datePattern, nowdate)) {
                    log.error("GtsInterbankRepoRevereseController getMinEnRateByHgDays Error occurred: 日期格式不正确，应为yyyy-mm-dd");
                    return R.failed("日期格式不正确，应为yyyy-mm-dd");
                }
            }
            
            BigDecimal minEnRate = reverseRepoService.getMinEnRateByHgDays(hgDays, nowdate);
            
            if (minEnRate == null) {
                log.warn("GtsInterbankRepoRevereseController getMinEnRateByHgDays: 未找到符合条件的记录");
                return R.failed("未找到符合条件的记录");
            }
            
            log.info("GtsInterbankRepoRevereseController getMinEnRateByHgDays completed, minEnRate: {}", minEnRate);
            return R.ok(minEnRate);
        } catch (IllegalArgumentException e) {
            log.error("GtsInterbankRepoRevereseController getMinEnRateByHgDays Error occurred", e);
            return R.failed("查询失败：" + e.getMessage());
        } catch (Exception e) {
            log.error("GtsInterbankRepoRevereseController getMinEnRateByHgDays Error occurred", e);
            return R.failed("查询失败：" + e.getMessage());
        }
    }
}
