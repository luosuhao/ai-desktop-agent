package com.gtfund.cloud.gts.admin.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.gtfund.cloud.common.security.util.SecurityUtils;
import com.gtfund.cloud.gts.admin.dao.GtsInterbankRepoRevereseDao;
import com.gtfund.cloud.gts.admin.entity.GtsInterbankRepoReverese;
import com.gtfund.cloud.gts.admin.entity.GtsInterbankRepoRevereseConstants;
import com.gtfund.cloud.gts.admin.entity.repo.RepoElements;
import com.gtfund.cloud.gts.admin.service.GtsInterbankRepoRevereseService;
import com.gtfund.cloud.gts.admin.service.repo.RepoElementsService;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

@Slf4j
@Service
public class GtsInterbankRepoRevereseServiceImpl  implements GtsInterbankRepoRevereseService {

	@Autowired
	private GtsInterbankRepoRevereseDao gtsInterbankRepoRevereseDao;

	@Autowired
	private RepoElementsService repoElementsService;

    @Override
    public boolean add(GtsInterbankRepoReverese entity) {
        log.info("GtsInterbankRepoRevereseServiceImpl add start");
        
        if (StringUtils.isBlank(entity.getFundCode())) {
            log.error("GtsInterbankRepoRevereseServiceImpl add Error occurred: 基金代码不能为空");
            throw new IllegalArgumentException("基金代码不能为空");
        }
        
        if (StringUtils.isBlank(entity.getFundName())) {
            log.error("GtsInterbankRepoRevereseServiceImpl add Error occurred: 基金名称不能为空");
            throw new IllegalArgumentException("基金名称不能为空");
        }

		if (StringUtils.isBlank(entity.getRepoElementsId())) {
			log.error("GtsInterbankRepoRevereseServiceImpl add Error occurred: repoElementsId不能为空");
			throw new IllegalArgumentException("repoElementsId不能为空");
		}

        String userId = SecurityUtils.getUser().getUsername();
        Date now = new Date();
        
        entity.setCreateTime(null);
        entity.setCreateBy(userId);
        entity.setUpdateTime(null);
        entity.setUpdateBy(userId);
		entity.setId(null);

        boolean result = gtsInterbankRepoRevereseDao.save(entity);

		LambdaUpdateWrapper<RepoElements> updateWrapper = new LambdaUpdateWrapper<>();
		updateWrapper.set(RepoElements::getGtsInterbankRepoRevereseId, entity.getId())
				.eq(RepoElements::getId, entity.getRepoElementsId());      // 指定更新条件

		repoElementsService.update(updateWrapper);

        log.info("GtsInterbankRepoRevereseServiceImpl add completed, success: {]", result);
        return result;
    }

    @Override
    public boolean delete(String id, String repoElementsId) {
        log.info("GtsInterbankRepoRevereseServiceImpl delete start for id: {}, repoElementsId :{}", id, repoElementsId);
        
        if (StringUtils.isBlank(id)) {
            log.error("GtsInterbankRepoRevereseServiceImpl delete Error occurred: ID不能为空");
            throw new IllegalArgumentException("ID不能为空");
        }

        GtsInterbankRepoReverese entity = gtsInterbankRepoRevereseDao.getById(id);
        
        if (entity == null) {
            log.error("GtsInterbankRepoRevereseServiceImpl delete Error occurred: 记录不存在");
            throw new IllegalArgumentException("记录不存在");
        }

        if (GtsInterbankRepoRevereseConstants.IS_DELETE_YES.equals(entity.getIsDelete())) {
            log.error("GtsInterbankRepoRevereseServiceImpl delete Error occurred: 记录已被删除");
            throw new IllegalArgumentException("记录已被删除");
        }

        entity.setIsDelete(GtsInterbankRepoRevereseConstants.IS_DELETE_YES);
        entity.setUpdateTime(new Date());
        entity.setUpdateBy(SecurityUtils.getUser().getUsername());

        boolean result = gtsInterbankRepoRevereseDao.updateById(entity);

        if (StringUtils.isNotBlank(repoElementsId)) {
			LambdaUpdateWrapper<RepoElements> updateWrapper = new LambdaUpdateWrapper<>();
			updateWrapper.set(RepoElements::getGtsInterbankRepoRevereseId, null) // 显式声明要将 id 设为 null
					.eq(RepoElements::getId, repoElementsId);      // 指定更新条件

			repoElementsService.update(updateWrapper);
		}
        
        log.info("GtsInterbankRepoRevereseServiceImpl delete completed, success: {]", result);
        return result;
    }

	@Override
	public boolean approval(String id, String isApproval) {
		log.info("GtsInterbankRepoRevereseServiceImpl approval start for id: {]", id);

		if (StringUtils.isBlank(id)) {
			log.error("GtsInterbankRepoRevereseServiceImpl approval Error occurred: ID不能为空");
			throw new IllegalArgumentException("ID不能为空");
		}

		GtsInterbankRepoReverese entity = gtsInterbankRepoRevereseDao.getById(id);

		if (entity == null) {
			log.error("GtsInterbankRepoRevereseServiceImpl approval Error occurred: 记录不存在");
			throw new IllegalArgumentException("记录不存在");
		}

		if (GtsInterbankRepoRevereseConstants.IS_DELETE_YES.equals(entity.getIsDelete())) {
			log.error("GtsInterbankRepoRevereseServiceImpl approval Error occurred: 记录已被删除");
			throw new IllegalArgumentException("记录已被删除");
		}

		entity.setIsApproval(isApproval);
		entity.setUpdateTime(new Date());
		entity.setUpdateBy(SecurityUtils.getUser().getUsername());

		boolean result = gtsInterbankRepoRevereseDao.updateById(entity);

		log.info("GtsInterbankRepoRevereseServiceImpl approval completed, success: {]", result);
		return result;
	}

    @Override
    public IPage<GtsInterbankRepoReverese> queryByDate(Page<GtsInterbankRepoReverese> page, String nowDay) {
        log.info("GtsInterbankRepoRevereseServiceImpl queryByDate start for nowDay: {]", nowDay);

        QueryWrapper<GtsInterbankRepoReverese> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq(GtsInterbankRepoRevereseConstants.COL_IS_DELETE, GtsInterbankRepoRevereseConstants.IS_DELETE_NO);
        
        if (StringUtils.isNotBlank(nowDay)) {
            queryWrapper.eq(GtsInterbankRepoRevereseConstants.COL_NOW_DAY, nowDay);
        }
        
        queryWrapper.orderByAsc(GtsInterbankRepoRevereseConstants.COL_IS_APPROVAL).orderByDesc(GtsInterbankRepoRevereseConstants.COL_CREATE_TIME);

        IPage<GtsInterbankRepoReverese> resultPage = gtsInterbankRepoRevereseDao.page(page, queryWrapper);
        
        log.info("GtsInterbankRepoRevereseServiceImpl queryByDate completed");
        return resultPage;
    }

    @Override
    public GtsInterbankRepoReverese getByIdWithCheck(String id) {
        log.info("GtsInterbankRepoRevereseServiceImpl getByIdWithCheck start for id: {]", id);
        
        if (StringUtils.isBlank(id)) {
            log.error("GtsInterbankRepoRevereseServiceImpl getByIdWithCheck Error occurred: ID不能为空");
            throw new IllegalArgumentException("ID不能为空");
        }

        GtsInterbankRepoReverese entity = gtsInterbankRepoRevereseDao.getById(id);
        
        if (entity == null || GtsInterbankRepoRevereseConstants.IS_DELETE_YES.equals(entity.getIsDelete())) {
            log.error("GtsInterbankRepoRevereseServiceImpl getByIdWithCheck Error occurred: 记录不存在或已被删除");
            throw new IllegalArgumentException("记录不存在或已被删除");
        }

        log.info("GtsInterbankRepoRevereseServiceImpl getByIdWithCheck completed");
        return entity;
    }

    @Override
    public Map<String, Object> getDictionary(String nowDay) {
        log.info("GtsInterbankRepoRevereseServiceImpl getDictionary start for nowDay: {]", nowDay);
        
        Map<String, Object> resultMap = new HashMap<>();
        
        QueryWrapper<GtsInterbankRepoReverese> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq(GtsInterbankRepoRevereseConstants.COL_IS_DELETE, GtsInterbankRepoRevereseConstants.IS_DELETE_NO);
        
        if (StringUtils.isNotBlank(nowDay)) {
            queryWrapper.eq(GtsInterbankRepoRevereseConstants.COL_NOW_DAY, nowDay);
        }
        
        List<GtsInterbankRepoReverese> list = gtsInterbankRepoRevereseDao.list(queryWrapper);
        
        Set<Map<String, String>> createBySet = new LinkedHashSet<>();
        Set<Map<String, String>> fundSet = new LinkedHashSet<>();
        
        for (GtsInterbankRepoReverese entity : list) {
            if (StringUtils.isNotBlank(entity.getCreateBy())) {
                Map<String, String> createByMap = new HashMap<>();
                createByMap.put("code", entity.getCreateBy());
                createByMap.put("name", entity.getCreateBy());
                createBySet.add(createByMap);
            }
            
            if (StringUtils.isNotBlank(entity.getFundCode()) && StringUtils.isNotBlank(entity.getFundName())) {
                Map<String, String> fundMap = new HashMap<>();
                fundMap.put("fundCode", entity.getFundCode());
                fundMap.put("fundName", entity.getFundName());
                fundSet.add(fundMap);
            }
        }
        
        resultMap.put("createByList", new ArrayList<>(createBySet));
        resultMap.put("fundList", new ArrayList<>(fundSet));
        
        log.info("GtsInterbankRepoRevereseServiceImpl getDictionary completed");
        return resultMap;
    }
}
