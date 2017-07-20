# -*- coding: utf-8 -*-

import re
import scrapy
from fake_useragent import UserAgent

from digit_phone import settings
from digit_phone.util import ExtractorPhoneSuning, save_db


class SuningPhoneSpider(scrapy.Spider):
    name = 'suning_phone'
    custom_settings = {'ROBOTSTXT_OBEY': False}

    def start_requests(self):
        pages = 100
        base_url = 'http://list.suning.com/emall/showProductList.do?ci=20006&pg=03&' \
                   'cp={p}&il=0&iy=0&adNumber=0&n=1&sesab=B&id=IDENTIFYING&cc=021'

        headers = {'Host': 'list.suning.com', 'Upgrade-Insecure-Requests': '1'}

        for page in range(pages):
            url = base_url.format(p=page)
            headers['User-Agent'] = UserAgent().random
            yield scrapy.Request(url, headers=headers)
            break

    def parse(self, response):
        for sel in response.css('div#filter-results li.product.subcode-add-type'):
            product_url = sel.css('div.res-info p.sell-point a::attr(href)').extract_first()
            next_url = response.urljoin(product_url)

            yield scrapy.Request(next_url, callback=self.parse_multi_cell)
            break

    def parse_multi_cell(self, response):
        multi_sku = False
        url = response.url
        url_regex = re.compile(r'/\d+\.html$')
        pre_skuid_regex = re.compile(r'/(\d+)/(\d+)\.html$')
        mobile_parameter = ExtractorPhoneSuning(response)

        versions_css = None

        if not mobile_parameter.is_smart_mobile:
            return

        pre_skuid_result = pre_skuid_regex.findall(url)
        pre_sku, skuid_t = pre_skuid_result[0]

        for ver_css, v_text_list, sku_css in settings.SUNING_VERSIONS:
            goto = False
            versions_text = (response.css(ver_css).extract_first() or '').replace(' ', '')

            for v_text in v_text_list:
                color_expr = 'colorItemList' in ver_css and u'颜色' in versions_text \
                             and re.compile(ur'\d+G').search(versions_text)

                if v_text in versions_text or color_expr:
                    goto = True
                    versions_css = sku_css
                    break

            if goto:
                break

        if versions_css is not None:
            sku_list = response.css(versions_css + '::attr(sku)').extract()
            version_list = response.css(versions_css + '::attr(title)').extract()

            assert len(sku_list) == len(version_list), " error url:[{}], versions_css: [{}], {}|{}".format(
                url, versions_css, sku_list, version_list)

            for index, skuid in enumerate(sku_list):
                if not multi_sku:
                    multi_sku = True

                next_url = url_regex.sub('/{}.html'.format(skuid), url)
                meta = {
                    'cell_version': version_list[index], 'use_selenium': True,
                    'skuid': skuid, 'pre_sku': pre_sku
                }

                yield scrapy.Request(next_url, meta=meta, callback=self.parse_detail)
                # break

        if not multi_sku or not versions_css:
            print
            response.meta.update({'pre_sku': pre_sku, 'skuid':  skuid_t})
            self.parse_detail(response)

    def parse_detail(self, response):
        item = {}
        skuid = response.meta['skuid']
        pre_sku = response.meta['pre_sku']

        mobile_parameter = ExtractorPhoneSuning(response)
        item.update(mobile_parameter.phone_base_info)

        cell_version = response.meta.get('cell_version', '')
        shangpin_item = response.css('span#productName a::text').extract_first() or ''
        shangpin_name = ''.join(response.css('h1#itemDisplayName *::text').extract())
        shangpin_price = response.css('.mainprice::text').extract_first()

        if shangpin_price:
            price = shangpin_price + (response.css('span.mainprice > span::text').extract_first() or '00')
        else:
            price = '0.00'

        yanbao = response.css('dl#yanbao > dd > ul > li:not(li.mulit) > a > span::text,'
                              'dl#yanbao > dd > ul > li.mulit > div.child-list > a > label::text'
                              ).extract()

        item.update({
            'cell_version': cell_version, 'shangpin_item': shangpin_item, 'price': price,
            'shangpin_name': shangpin_name, 'yanbao': yanbao, 'skuid': skuid, 'pre_sku': pre_sku
        })

        save_db(self, item)


if __name__ == '__main__':
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    crawler = CrawlerProcess(get_project_settings())
    crawler.crawl(SuningPhoneSpider)
    crawler.start()
