# -*- coding: utf-8 -*-

import re
import scrapy

from pymongo import MongoClient
client = MongoClient()
database = 'digit'
collections_cache = {}
filter_cache = {}


def retry(response, callback):
    request = None
    timeout_m = re.compile(r'setTimeout', re.S).search(response.body)
    max_download_count = response.meta.get('max_download_count', 1)

    if timeout_m and response.status == 200:
        if max_download_count <= 5:
            response.meta['max_download_count'] = max_download_count + 1
            request = scrapy.Request(
                url=response.url, callback=callback, cookies=response.request.cookies,
                headers=response.request.headers, meta=response.meta, dont_filter=True
            )
    return request


def save_db(spider, data):
    if spider.name not in collections_cache:
        collections_cache[spider.name] = client[database][spider.name]

    coll = collections_cache[spider.name]

    if spider.name not in filter_cache:
        filter_cache[spider.name] = {doc['skuid'] for doc in coll.find()}

    filter_set = filter_cache[spider.name]

    if data['skuid'] not in filter_set:
        coll.insert_one(data)


class ExtractorPhoneSuning(object):
    def __init__(self, response):
        self.response = response
        self._cache_property = self.phone_parameter

    @property
    def phone_parameter(self):
        data = {}
        pre_key = None

        for tr_sel in self.response.css('table#itemParameter tr'):
            th_text = tr_sel.css('th::text').extract_first()

            if th_text:
                pre_key = th_text
            else:
                k_text = tr_sel.css('td.name > div > span::text').extract_first() or ''
                v_text = tr_sel.css('td.val *::text').extract_first() or ''
                k_text and data.setdefault(pre_key, []).append([k_text, v_text])

        return data

    @property
    def is_smart_mobile(self):
        base_parameter = {}

        for key, values in self._cache_property.items():
            base_parameter.update(dict(values))

        for k, v in base_parameter.items():
            if u'手机操作系统' in k:
                return u'非智能手机' not in v

        return True

    @property
    def phone_base_info(self):
        data = {}

        for key, values in self._cache_property.items():
            if u'主体' in key:
                data['body'] = dict(values)

            if u'屏幕' in key:
                data['screen'] = dict(values)

        return data


