# -*- coding:utf-8 -*-
from lxml import etree
import re
from copy import deepcopy

from JavHelper.core.jav_scraper import JavScraper
from JavHelper.core import JAVNotFoundException
from JavHelper.core.requester_proxy import return_html_text, return_post_res, return_get_res
from JavHelper.core.utils import re_parse_html, re_parse_html_list_field, defaultlist
from JavHelper.core.ini_file import return_config_string
from JavHelper.core.utils import parsed_size_to_int


class JavBusScraper(JavScraper):
    def __init__(self, *args, **kwargs):
        super(JavBusScraper, self).__init__(*args, **kwargs)
        self.source = 'javbus'
        self.xpath_dict = {
            'search_field': {
                'title': '//a[@class="bigImage"]/img/@title',
                'studio': '//p[span="製作商:"]/a/text()',
                'premiered': '//p[span="發行日期:"]/text()',
                #'year': processed from release date
                'length': '//p[span="長度:"]/text()',
                'director': '//p[span="導演:"]/a/text()',
                'image': '//a[@class="bigImage"]/img/@src',
                #'score': no good source
            },
            'search_list_field': {
                #'plot': no good source,
                'all_actress': '//span[@class="genre" and @onmouseover]/a/text()',
                'genres': '//span[@class="genre"]/a[contains(@href, "genre")]/text()'
            },
        }

        self.jav_url = return_config_string(['其他设置', 'javbus网址'])

    def postprocess(self):
        if self.jav_obj.get('premiered'):
            self.jav_obj['premiered'] = self.jav_obj['premiered'].lstrip(' ')
            self.jav_obj['year'] = self.jav_obj['premiered'][:4]
        if self.jav_obj.get('image'):
            # get rid of https to have consistent format with other sources
            self.jav_obj['image'] = self.jav_obj['image'].lstrip('https:').lstrip('http:')
        if self.jav_obj.get('length'):
            self.jav_obj['length'] = self.jav_obj['length'].lstrip(' ')[:-2]
        if self.jav_obj.get('title'):
            self.jav_obj['title'] = '{} {}'.format(self.jav_obj['car'], self.jav_obj['title'])

    def get_single_jav_page(self):
        """
        This search method is currently NOT DETERMINISTIC!
        Example: SW-098 -> has 3 outputs
        """

        # perform search first
        # https://www.javbus.com/search/OFJE-235&type=&parent=ce
        search_url = self.jav_url + 'search/{}&type=&parent=ce'.format(self.car)
        print(f'accessing {search_url}')

        jav_search_content = return_get_res(search_url).content
        search_root = etree.HTML(jav_search_content)

        search_results = search_root.xpath('//a[@class="movie-box"]/@href')

        if not search_results:
            # sometimes the access will fail, try directly access by car
            direct_url = self.jav_url + self.car
            print(f'no search result, try direct accessing {search_url}')
            jav_search_content = return_get_res(direct_url).content
            search_root = etree.HTML(jav_search_content)

            if search_root.xpath('//a[@class="bigImage"]/img/@title'):
               search_results = [direct_url]

        if not search_results:
            raise JAVNotFoundException('{} cannot be found in javbus'.format(self.car))

        self.total_index = len(search_results)
        result_first_url = search_results[self.pick_index]

        return return_get_res(result_first_url).content, self.total_index


def javbus_magnet_search(car: str):
    jav_url = return_config_string(['其他设置', 'javbus网址'])
    gid_match = r'.*?var gid = (\d*);.*?'
    magnet_xpath = {
        'magnet': '//tr/td[position()=1]/a[1]/@href',
        'title': '//tr/td[position()=1]/a[1]/text()',
        'size': '//tr/td[position()=2]/a[1]/text()'
    }
    main_url_template = jav_url+'{car}'
    magnet_url_template = jav_url+'ajax/uncledatoolsbyajax.php?gid={gid}&uc=0'

    res = return_get_res(main_url_template.format(car=car)).text
    gid = re.search(gid_match, res).groups()[0]

    res = return_get_res(magnet_url_template.format(gid=gid), headers={'referer': main_url_template.format(car=car)}).content
    root = etree.HTML(res)

    magnets = defaultlist(dict)
    for k, v in magnet_xpath.items():
        _values = root.xpath(v)
        for _i, _value in enumerate(_values):
            magnets[_i].update({k: _value.strip('\t').strip('\r').strip('\n').strip()})
            if k == 'size':
                magnets[_i].update({'size_sort': parsed_size_to_int(_value.strip('\t').strip('\r').strip('\n').strip())})
    
    return magnets


def javbus_set_page(page_template: str, page_num=1, url_parameter=None, config=None) -> dict:
    xpath_dict = {
        'title': '//div[@class="photo-frame"]/img[not(contains(@src, "actress"))]/@title',
        'javid': '//div[@class="photo-info"]/span/date[1]/text()',
        'img': '//div[@class="photo-frame"]/img[not(contains(@src, "actress"))]/@src',
        'car': '//div[@class="photo-info"]/span/date[1]/text()'
    }
    xpath_max_page = '//ul[@class="pagination pagination-lg"]/li/a/text()'

    # force to get url from ini file each time
    javbus_url = return_config_string(['其他设置', 'javbus网址'])
    set_url = javbus_url + page_template.format(page_num=page_num, url_parameter=url_parameter)
    print(f'accessing {set_url}')

    res = return_post_res(set_url).content
    root = etree.HTML(res)

    jav_objs_raw = defaultlist(dict)
    for k, v in xpath_dict.items():
        _values = root.xpath(v)
        for _i, _value in enumerate(_values):
            jav_objs_raw[_i].update({k: _value})

    try:
        max_page = root.xpath(xpath_max_page)[-2]
    except:
        max_page = page_num
    if not max_page:
        max_page = page_num
    
    return jav_objs_raw, max_page
