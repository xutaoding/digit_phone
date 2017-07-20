# -*- coding: utf-8 -*-

import sys
import json
import os.path
import requests
from copy import deepcopy

import scrapy
from fake_useragent import UserAgent

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from digit_phone.util import retry, save_db


class JdPhoneSpider(scrapy.Spider):
    name = 'jd_phone'

    def start_requests(self):
        pages = 147
        base_url = 'https://list.jd.com/list.html?' \
                   'cat=9987,653,655&page={page}&sort=sort_rank_asc&trans=1&JL=6_0_0#J_main'

        headers = {
            ':authority': 'list.jd.com',
            ':method': 'GET',
            ':path': '/list.html?cat=9987,653,655&page={page}&sort=sort_rank_asc&trans=1&JL=6_0_0',
            ':scheme': 'https',
            'accept-encoding': 'gzip, deflate, sdch, br',
            'referer': 'https://list.jd.com/list.html?cat=9987,653,655&page={page}&sort=sort_rank_asc&trans=1&JL=6_0_0',
            'upgrade-insecure-requests': '1',
        }

        for page in range(2, pages + 1):
            copy_headers = deepcopy(headers)
            copy_headers['user-agent'] = UserAgent().random
            copy_headers[':path'] = copy_headers[':path'].format(page=page)

            if page != 1:
                copy_headers['referer'] = copy_headers['referer'].format(page=page - 1)
            else:
                copy_headers['referer'] = 'https://list.jd.com/list.html?cat=9987,653,655'

            url = base_url.format(page=page)
            yield scrapy.Request(url, headers=copy_headers)
            # break

    def parse(self, response):
        # request = retry(response, self.parse)
        # if request is not None:
        #     yield request
        #     return

        for sel in response.css('div#plist li.gl-item > div.gl-i-wrap.j-sku-item::attr(data-sku)'):
            skuid = sel.extract().strip()
            if not skuid:
                continue

            url = 'https://item.jd.com/{}.html'.format(skuid)
            meta = {'skuid': skuid}
            yield scrapy.Request(url, meta=meta, headers=response.request.headers, callback=self.parse_detail)
            # break

    def parse_detail(self, response):
        skuid = response.meta['skuid']

        # request = retry(response, self.parse)
        # if request is not None:
        #     yield request
        #     return

        shangpin_item = response.css('div.item.ellipsis::text').extract_first() or ''
        shangpin_name = response.css('div.sku-name::text').extract_first() or ''
        shangpin_color = response.css('div#choose-attr-1 > div.dd > div.item::attr(data-value)').extract()
        versions = response.css('div#choose-attr-2 > div.dd > div.item::attr(data-value)').extract()

        response.meta.update({
            'shangpin_item': shangpin_item.strip(),
            'shangpin_name': shangpin_name.strip(),
            'shangpin_color': shangpin_color, 'versions': versions
        })

        # 京东国内
        for sel in response.css('div.Ptable-item'):
            text = sel.css('h3::text').extract_first() or ''
            body = u'主体' in text
            screen = u'屏幕' in text

            if body or screen:
                _from = 'body' if body else ('screen' if screen else None)
                keys = [(s or '').strip() for s in sel.css('dl dt::text').extract()]
                values = [(s or '').strip() for s in sel.css('dl dd::text').extract()]

                phone_dict = dict(zip(keys, values))
                response.meta.update({_from: phone_dict})

        # 京东全球购
        pre_key = ''
        global_info = {}
        for t_sel in response.css('table.Ptable tr'):
            th_text = (t_sel.css('th::text').extract_first() or '').strip()
            if th_text:
                pre_key = th_text
            else:
                global_info.setdefault(pre_key, []).append(t_sel.css('td::text').extract())

        print skuid, global_info
        _from = {
            u'主体' in k and 'body' or (u'屏幕' in k and 'screen') or '': dict([_v for _v in v if _v])
            for k, v in global_info.items() if u'主体' in k or u'屏幕' in k
        }
        print skuid, _from
        _from and response.meta.update({k: v for k, v in _from.items() if k})

        price_url = 'https://p.3.cn/prices/mgets?callback=&type=1&area=1_72_4137_0&' \
                    'pdtk=&pduid=1500429410217979835051&pdpin=&pin=null&pdbp=0&skuIds={skuid}&' \
                    'ext=11000000&source=item-pc'

        req_headers = {hk: ';'.join(hv) for hk, hv in response.request.headers.items() if hk[0] != ':'}
        resp = requests.get(price_url.format(skuid='J_' + skuid), headers=req_headers)
        json_data = resp.content.replace(';', '')[2:-3]
        p_data = json.loads(json_data)

        response.meta.update(price=p_data['p'])
        yanbap_url = 'https://cd.jd.com/yanbao/v3?skuId={skuid}&cat=9987,653,655&' \
                     'area=1_72_4137_0&brandId=12669&callback=yanbao'
        headers = {
            'Connection': 'keep-alive',
            'Host': 'cd.jd.com',
            'Referer': 'https://item.jd.com/{}.html'.format(skuid),
            'User-Agent': UserAgent().random,
        }

        yield scrapy.Request(
            yanbap_url.format(skuid=skuid), meta=response.meta,
            headers=headers, callback=self.parse_yanbao
        )

    def parse_yanbao(self, response):
        # request = retry(response, self.parse)
        # if request is not None:
        #     yield request
        #     return

        yanbao = []
        resp = response.body.decode('gbk')
        json_data = resp[7:-1]

        if not json_data:
            data = []
        else:
            data = json.loads(json_data)[response.meta['skuid']]

        for item in data:
            yb = []

            for detail in item['details']:
                yb_name = detail['bindSkuName']
                yb_price = detail['price']

                yb_info = yb_name + ' ' + str(yb_price)
                yb.append(yb_info)

            yanbao.append(yb)

        jd_item = {
            'skuid': response.meta['skuid'], 'price': response.meta['price'],
            'shangpin_item': response.meta['shangpin_item'], 'shangpin_name': response.meta['shangpin_name'],
            'shangpin_color': response.meta['shangpin_color'], 'body': response.meta['body'],
            'screen': response.meta.get('screen', {}),
            'yanbao': yanbao, 'versions': response.meta['versions']
        }

        save_db(self, jd_item)


if __name__ == '__main__':
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    crawler = CrawlerProcess(get_project_settings())
    crawler.crawl(JdPhoneSpider)
    crawler.start()


