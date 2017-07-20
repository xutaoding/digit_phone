# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/spider-middleware.html

from datetime import datetime
from scrapy import signals
from scrapy.http.response.text import TextResponse
import scrapy.downloadermiddlewares.httpcache
from selenium import webdriver


class DigitPhoneSpiderMiddleware(object):
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, dict or Item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Response, dict
        # or Item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class DigitPhoneDownloaderMiddleware(object):
    @classmethod
    def from_crawler(cls, crawler):
        o = cls()
        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(o.spider_closed, signal=signals.spider_closed)

        return o

    def spider_opened(self, spider):
        desired_capabilities = {
            'browserName': 'firefox', 'platform': "LINUX", 'version': "52.2.0"
        }

        print 'start driver:', datetime.now()
        self.driver = webdriver.Remote(
            command_executor='http://192.168.216.168:4444/wd/hub',
            desired_capabilities=desired_capabilities
        )
        self.driver.set_page_load_timeout(60)

    def spider_closed(self, spider):
        self.driver.quit()
        print 'close driver:', datetime.now()

    def process_request(self, request, spider):
        # 但是这样不能保持并发， 只能一个一个url， 如何改进
        if spider.name == 'suning_phone' and request.meta.get('use_selenium'):
            print 'Now use selenium grid:', datetime.now(), id(self.driver)

            self.driver.get(request.url)
            html = self.driver.page_source

            return TextResponse(request.url, encoding='utf-8', body=html, request=request)

