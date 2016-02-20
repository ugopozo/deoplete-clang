import os
import re
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from helper import load_external_module
from profiler import timeit

from deoplete.sources.base import Base

load_external_module('clang')
import clang.cindex as clang

from logging import getLogger
logger = getLogger(__name__)


class Source(Base):

    def __init__(self, vim):
        Base.__init__(self, vim)

        self.name = 'clang'
        self.mark = '[clang]'
        self.filetypes = ['c', 'cpp', 'objc', 'objcpp']
        # TODO(zchee): not need "r'[a-zA-Z_]\w*::\w*'" in C
        self.input_pattern = (r'[^. \t0-9]\.\w*|'
                              r'[^. \t0-9]->\w*|'
                              r'[a-zA-Z_]\w*::\w*')
        self.rank = 500

        # Load libclang shared library
        library_path = self.vim.vars['deoplete#sources#clang#libclang_path']
        clang.Config.set_library_path(library_path)
        clang.Config.set_compatibility_check(False)
        self.clang_header = \
            self.vim.vars['deoplete#sources#clang#clang_header']

        if self.vim.vars['deoplete#debug']:
            logfile = self.vim.vars['deoplete#sources#clang#debug_log']
            self.log(logfile)

    # @timeit(fmt='simple', threshold=[0.00003000, 0.00015000])
    def get_complete_position(self, context):
        m = re.search(r'\w*$', context['input'])
        return m.start() if m else -1

    @timeit(fmt='simple', threshold=[0.1, 0.2], logger=logger)
    def gather_candidates(self, context):
        line, col = self.vim.current.window.cursor
        f = self.vim.current.buffer.name
        index = clang.Index.create()
        translation_unit = index.parse(f, ['-x', 'c++', '-std=c++11'])

        complete = translation_unit.codeComplete(f, line, col)
        result = list(map(self.parse_candidates, complete.results))
        # logger.debug('\n'.join('{}: {}'.format(*k)
        #                        for k in enumerate(list(complete.results))))

        return result

    # @timeit(fmt='verbose', threshold=[0.00000500, 0.00002000])
    def parse_candidates(self, result):
        completion = dict()
        _type = ""
        word = ""
        abbr = ""
        kind = ""
        info = ""

        for chunk in result.string:
            chunk_spelling = chunk.spelling

            if chunk.isKindInformative() or chunk.isKindComma() or \
                    chunk_spelling is None or chunk.isKindPlaceHolder():
                continue

            elif chunk.isKindResultType():
                _type += chunk_spelling
                continue

            elif chunk.isKindTypedText():
                abbr += chunk_spelling

            word += chunk_spelling
            info += chunk_spelling

        completion['word'] = word
        completion['abbr'] = abbr
        completion['info'] = info
        completion['dup'] = 0

        if result.cursorKind in ClangData.kinds:
            completion['kind'] = ' '.join(
                [ClangData.kinds[result.cursorKind], _type, kind])
        else:
            completion['kind'] = ' '.join(
                [str(result.cursorKind), _type, kind])

        return completion

    def log(self, path):
        from logging import FileHandler, Formatter, DEBUG
        hdlr = FileHandler(os.path.expanduser(path))
        logger.addHandler(hdlr)
        fmt = Formatter('%(levelname)s %(message)s')
        hdlr.setFormatter(fmt)
        logger.setLevel(DEBUG)