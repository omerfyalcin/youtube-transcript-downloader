#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import json
import html
import sys
import getopt


def videoId2url(videoId):
    return 'https://www.youtube.com/watch?v=' + videoId


def url2soup(url):
    t = requests.get(url).text
    try:
        soup = BeautifulSoup(t, 'lxml')
    except BaseException:
        soup = BeautifulSoup(t, 'html.parser')
    return soup


def soup2script(soup):
    return soup.find_all("script")


def script2dict(script_text):
    start = script_text.index("{")
    end = script_text.rindex("}")
    d = json.loads(script_text[start:end + 1])
    return d


def meta_data(scripts):
    ct_script = [
        script for script in scripts if "captionTracks" in str(script)]
    if len(ct_script) == 0:
        return []
    assert len(ct_script) == 1
    ct_dict = script2dict(str(ct_script[0]))
    md = ct_dict["captions"]["playerCaptionsTracklistRenderer"]["captionTracks"]
    return md


def detect_problem(scripts):
    error_script = [
        script for script in scripts if "playerErrorMessageRenderer" in str(script)]
    assert len(error_script) == 1
    error_dict = script2dict(str(error_script[0]))
    error_message = error_dict['playabilityStatus']['errorScreen']['playerErrorMessageRenderer']['subreason']['simpleText']
    return error_message


def sort_through_md(md, langCode=None, lang=None, priority=None):

    if langCode is None and lang is None:
        langCodes = [item['languageCode'][:2] for item in md]
        if len(set(langCodes)) != 1:
            raise Exception(
                "Captions in more than one language available. \n Please specify a language or a languageCode")
        else:
            langCode = langCodes[0]

    if priority is None:
        if langCode == 'en':
            priority = ["en-US", 'en', "en-CA", "en-GB"]
        else:
            priority = []

    if langCode is not None:
        items = [item for item in md if item['languageCode'][:2] == langCode]

    if lang is not None:
        items = [item for item in md if lang.lower() in item['name']
                 ['simpleText'].lower()]

    if len(items) == 0:
        return None

    nonauto_items = [
        item for item in items if '(auto-generated)' not in item['name']['simpleText']]
    auto_items = [
        item for item in items if '(auto-generated)' in item['name']['simpleText']]

    if len(nonauto_items) > 1:

        derived_langCode = nonauto_items[0]['languageCode'][:2]

        if derived_langCode not in priority:
            priority.append(derived_langCode)

        code_v_item = {item['languageCode']: item for item in nonauto_items}

        while len(priority) > 0:
            p = priority.pop(0)
            try:
                preferred_item = code_v_item[p]
                return preferred_item
            except BaseException:
                pass

        return [nonauto_items[0]]

    elif len(nonauto_items) == 1:
        preferred_item = nonauto_items[0]
        return preferred_item

    else:
        assert len(items) == 1
        assert '(auto-generated)' in items[0]['name']['simpleText']
        preferred_item = items[0]
        return preferred_item


def extract_xml_urls(preferred_items):
    return preferred_items['baseUrl']


def extract_lines(xml_url):
    soup = url2soup(xml_url)
    text_tags = soup.find_all("text")
    lines = []
    for tag in text_tags:
        line = tag.text
        if '\n' in line:
            lines = lines + line.split('\n')
        else:
            lines = lines + [line]
    return lines


def clean(lines):
    return [html.unescape(line).replace(u'\xa0', u' ') for line in lines]


def cc(videoId, langCode=None, lang=None, meta=False):

    if lang is not None and langCode is not None:
        raise Exception(
            "Specify either a language or a languageCode, not both.")

    url = videoId2url(videoId)
    soup = url2soup(url)
    scripts = soup2script(soup)
    md = meta_data(scripts)
    if len(md) == 0:
        try:
            error_message = detect_problem(scripts)
            if meta:
                return {'not_available': error_message}
            else:
                print(error_message)
                return None
        except BaseException:
            if meta:
                return {
                    'not_available': 'No CC available for this video in any language.'}
            else:
                print("No CC available for this video in any language.")
                return None
    preferred_items = sort_through_md(md, langCode=langCode, lang=lang)
    if preferred_items is None:
        if meta:
            return {
                'not_available': 'No CC available for this video in this language.'}
        else:
            print('No CC available for this video in this language.')
            return None

    xml_urls = extract_xml_urls(preferred_items)
    lines_list = extract_lines(xml_urls)
    cleaned = clean(lines_list)

    if meta:
        results = {'languageCode': preferred_items['languageCode'],
                   'language': preferred_items['name']['simpleText'],
                   'text': cleaned}
    else:
        results = cleaned
    return results


def main():
    argumentList = sys.argv[1:]
    options = 'v:l:c:f:m'
    long_options = ['id=', 'lang=', 'langCode=', 'filename=', 'meta']
    arguments, values = getopt.getopt(argumentList, options, long_options)

    lang = None
    langCode = None
    file_name_not_provided = True
    create_meta_data = False

    for currentArgument, currentValue in arguments:

        if currentArgument in ("-v", "--videoId"):
            videoId = currentValue

        elif currentArgument in ("-l", "--lang"):
            lang = currentValue

        elif currentArgument in ("-c", "--langCode"):
            langCode = currentValue

        elif currentArgument in ("-f", "--filename"):
            file_name = current_value
            file_name_not_provided = False

        elif currentArgument in ("-m", "--meta"):
            create_meta_data = True

    if file_name_not_provided:
        txt_path = videoId + '.txt'
        json_path = videoId + '.json'
    else:
        txt_path = file_name + '.txt'
        json_path = file_name + '.json'

    if create_meta_data:
        result = cc(videoId, lang=lang, langCode=langCode, meta=True)
        try:
            text = result.pop('text')
            with open(txt_path, 'w') as fp:
                fp.writelines("%s\n" % line for line in text)
            with open(json_path, 'w') as fp:
                json.dump(result, fp)
        except BaseException:
            with open(json_path, 'w') as fp:
                json.dump(result, fp)

    else:
        result = cc(videoId, lang=lang, langCode=langCode)
        try:
            text = result
            with open(txt_path, 'w') as fp:
                fp.writelines("%s\n" % line for line in text)
        except BaseException:
            with open(json_path, 'w') as fp:
                json.dump(result, fp)


if __name__ == '__main__':
    main()
