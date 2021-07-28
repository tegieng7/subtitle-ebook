import json
import logging
import os
import re
from pathlib import Path

import lxml.html
import requests
from ebooklib import epub
from pysubparser import parser

logger = logging.getLogger(__name__)

TVDB = 'https://www.thetvdb.com/series/{title}/allseasons/official'


def get_series_info(title):
    """Get series info from TVDB

    Args:
        title (str): series name

    Returns:
        dict: series data 
    """
    def __text(item, css):
        lst = [i.text_content().strip() for i in item.cssselect(css)]
        return ' '.join(lst)

    url = TVDB.format(title=title)
    r = requests.get(url)
    root = lxml.html.fromstring(r.content)

    data = {}

    selector = '.list-group > .list-group-item'
    for item in root.cssselect(selector):
        episode = __text(item, '.episode-label')
        data.update({
            episode: {
                'title': __text(item, '.list-group-item-heading > a'),
                'description': __text(item, '.list-group-item-text')}

        })

    return data


def episode_html(filepath):
    """Convert subtile to html format.

    Args:
        filepath (str): path to subtile file

    Returns:
        str: subtitle in html format
    """
    logger.info(Path(filepath).name)
    # Get raw text from subtitle file
    lst_line = []
    for line in parser.parse(filepath):
        line = re.sub(r'\d+ > ', '', str(line))

        if lst_line and line[0].islower():
            line = '{0} {1}'.format(lst_line[-1], line)
            del lst_line[-1]

        lst_line.append(line)

    # Create html text
    html = u''
    for line in lst_line:
        line = lxml.html.fromstring(line).text_content()
        if line[0] == '[' and line[-1] == ']':
            line = '<i>{0}</i>'.format(line[1:-1])
        html += '<p>{0}</p>'.format(line)

    return html


def match_episode(filename, lst_pattern, lst_suffix):
    """Map filename to episode info.

    Args:
        filename (str): path to subtitle

    Returns:
        str: in format S01E01
    """
    logger.info(filename)

    se = None

    filename = filename.lower()
    suffix = Path(filename).suffix

    lst_pattern = lst_pattern.copy()
    pattern = lst_pattern.pop(-1)
    try:
        if suffix in lst_suffix:
            m = re.search(pattern, filename)
            season = int(m.group('season'))
            episode = int(m.group('episode'))
            se = 'S{0:02d}E{1:02d}'.format(season, episode)
    except:
        if lst_pattern:
            match_episode(filename, lst_pattern)

    return se


def prepare(title, dirpath, file_info):
    """Prepare info file before generating epub.

    Args:
        title (str): series name
        dirpath (str): path to subtile directory
        file_info (str): path to info file <title.json> in dirpath
    """
    try:
        with open(file_info) as fp:
            data = json.load(fp)
    except:
        file_default = Path(__file__).parent.joinpath('config.json')
        with open(file_default) as fp:
            data = json.load(fp)

    config = data.get('zconfig', {})
    lst_suffix = config.get('subtitleSuffix', [])
    lst_pattern = config.get('episodePattern', [])

    data_tv = get_series_info(title)

    for root, _, files in os.walk(dirpath):
        for filename in files:
            se = match_episode(filename, lst_pattern, lst_suffix)
            if se is not None:
                info = data_tv.get(se)
                info.update({
                    'subtitle': str(filename),
                    'root': root
                })
                data_tv.update({se: info})

    data.update({'tv': data_tv})

    with open(file_info, 'w') as fp:
        json.dump(data, fp, indent=4, sort_keys=True)


def generate(file_info, file_epub):
    with open(file_info) as fp:
        data_info = json.load(fp)

    data_tv = data_info.get('tv')
    book_info = data_info.get('bookInfo')

    book = epub.EpubBook()

    # set metadata
    book.set_title(book_info['title'])
    book.set_language('en')
    book.add_author(book_info['author'])

    # add cover image
    cover = epub.EpubCover(file_name='cover.jpeg')
    book.add_item(cover)

    file_cover = Path(file_info).parent.joinpath(book_info.get('cover'))
    with open(file_cover, 'rb') as fp:
        content = fp.read()
    cover_img = epub.EpubItem(file_name='cover.jpeg',
                              media_type='image/jpeg', content=content)
    book.add_item(cover_img)

    lst_spine = []
    toc = []
    s_prev_season = 0
    s_lst_episode = []
    for se, info in data_tv.items():
        if 'subtitle' not in info:
            continue

        title = '{0} - {1}'.format(se, info['title'])

        episode_intro = '<h2>{title}</h2><p><i>{description}</i></p>'
        episode_intro = episode_intro.format(
            title=title, description=info.get('description'))

        filepath = Path(info['root']).joinpath(info['subtitle'])
        content = episode_html(str(filepath))
        content = episode_intro + content

        if not content:
            raise Exception('Empty content', se)

        # Add chapter
        file_name = '{0}.xhtml'.format(se)

        chap = epub.EpubHtml(title=title, file_name=file_name, lang='en')
        chap.content = content

        lst_spine.append(chap)

        book.add_item(chap)

        # TOC
        m = re.search('S(?P<season>\d+)', se)
        season = int(m.group('season'))
        if season != s_prev_season:
            if s_lst_episode:
                s_toc = (
                    epub.Section('Season {0}'.format(s_prev_season)),
                    tuple(s_lst_episode)
                )
                toc.append(s_toc)

            s_lst_episode = [chap]
            s_prev_season = season
        else:
            s_lst_episode.append(chap)

    else:
        s_toc = (
            epub.Section('Season {0}'.format(s_prev_season)),
            tuple(s_lst_episode)
        )
        toc.append(s_toc)

    # define Table Of Contents
    book.toc = tuple(toc)

    # add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # basic spine
    lst_spine.insert(0, 'nav')
    book.spine = lst_spine

    # write to the file
    epub.write_epub(file_epub, book, {})
