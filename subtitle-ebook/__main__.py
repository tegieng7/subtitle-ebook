import argparse
import logging
from pathlib import Path

import generate

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(lineno)s:%(name)-s %(levelname)-s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler()]
)


parser = argparse.ArgumentParser(description='Subtitle commands')
parser.add_argument('action', metavar='<prepare|generate>')
parser.add_argument('title', metavar='<title>')
parser.add_argument('dirpath', metavar='<dirpath>')

args = parser.parse_args()

if __name__ == "__main__":
    action = args.action
    title = args.title
    dirpath = Path(args.dirpath).absolute()

    file_info = dirpath.joinpath('{0}.json'.format(title))
    file_epub = dirpath.joinpath('{0}.epub'.format(title))

    if action == 'prepare':
        generate.prepare(title, dirpath, file_info)

    elif action == 'generate':
        generate.generate(file_info, file_epub)
