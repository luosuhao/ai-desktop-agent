package com.gtfund.cloud.gts.admin.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.gtfund.cloud.gts.admin.entity.GtsInterbankRepoReverese;

import java.util.Map;

public interface GtsInterbankRepoRevereseService {

    boolean add(GtsInterbankRepoReverese entity);

    boolean delete(String id, String repoElementsId);

    IPage<GtsInterbankRepoReverese> queryByDate(Page<GtsInterbankRepoReverese> page, String nowDay);

    GtsInterbankRepoReverese getByIdWithCheck(String id);

    Map<String, Object> getDictionary(String nowDay);

	boolean approval(String id, String isApproval);
}
