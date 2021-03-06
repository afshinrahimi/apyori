#!/usr/bin/env python

"""
 simple implementation of Apriori algorithm by Python.
 The code is written by __author_email__. I just changed few things
 to customise it for my work.
"""

import sys
import csv
import argparse
import json
import os
import pdb
from collections import namedtuple
from itertools import combinations
from itertools import chain


# Meta informations.
__version__ = '1.1.1'
__author__ = 'Yu Mochizuki'
__author_email__ = 'ymoch.dev@gmail.com'
global_num_transaction = 0


################################################################################
# Data structures.
################################################################################
class TransactionManager(object):
    """
    Transaction managers.
    """

    def __init__(self, transactions, item_map=None):
        """
        Initialize.
        Arguments:
            transactions -- A transaction iterable object
                            (eg. [['A', 'B'], ['B', 'C']]).
        """
        self.__num_transaction = 0
        self.__items = []
        self.__transaction_index_map = {}
        self.__item_map = item_map
        for transaction in transactions:
            self.add_transaction(transaction)

    def add_transaction(self, transaction):
        """
        Add a transaction.
        Arguments:
            transaction -- A transaction as an iterable object (eg. ['A', 'B']).
        """
        for item in transaction:
            if self.__item_map:
                if self.__item_map in item:
                    item = self.__item_map
            if item not in self.__transaction_index_map:
                self.__items.append(item)
                self.__transaction_index_map[item] = set()
            self.__transaction_index_map[item].add(self.__num_transaction)
        self.__num_transaction += 1

    def calc_support(self, items):
        """
        Returns a support for items.
        Arguments:
            items -- Items as an iterable object (eg. ['A', 'B']).
        """
        # Empty items is supported by all transactions.
        if not items:
            return 1.0

        # Empty transactions supports no items.
        if not self.num_transaction:
            return 0.0

        # Create the transaction index intersection.
        sum_indexes = None
        for item in items:
            indexes = self.__transaction_index_map.get(item)
            if indexes is None:
                # No support for any set that contains a not existing item.
                return 0.0

            if sum_indexes is None:
                # Assign the indexes on the first time.
                sum_indexes = indexes
            else:
                # Calculate the intersection on not the first time.
                sum_indexes = sum_indexes.intersection(indexes)

        # Calculate and return the support.
        return float(len(sum_indexes)) / self.__num_transaction

    def initial_candidates(self):
        """
        Returns the initial candidates.
        """
        return [frozenset([item]) for item in self.items]

    @property
    def num_transaction(self):
        """
        Returns the number of transactions.
        """
        return self.__num_transaction

    @property
    def items(self):
        """
        Returns the item list that the transaction is consisted of.
        """
        return sorted(self.__items)

    @staticmethod
    def create(transactions, item_map=None):
        """
        Create the TransactionManager with a transaction instance.
        If the given instance is a TransactionManager, this returns itself.
        """
        if isinstance(transactions, TransactionManager):
            return transactions
        return TransactionManager(transactions, item_map)


# Ignore name errors because these names are namedtuples.
SupportRecord = namedtuple( # pylint: disable=C0103
    'SupportRecord', ('items', 'support'))
RelationRecord = namedtuple( # pylint: disable=C0103
    'RelationRecord', SupportRecord._fields + ('ordered_statistics',))
OrderedStatistic = namedtuple( # pylint: disable=C0103
    'OrderedStatistic', ('items_base', 'items_add', 'confidence', 'lift',))


################################################################################
# Inner functions.
################################################################################
def create_next_candidates(prev_candidates, length):
    """
    Returns the apriori candidates as a list.
    Arguments:
        prev_candidates -- Previous candidates as a list.
        length -- The lengths of the next candidates.
    """
    # Solve the items.
    item_set = set()
    for candidate in prev_candidates:
        for item in candidate:
            item_set.add(item)
    items = sorted(item_set)

    # Create the temporary candidates. These will be filtered below.
    tmp_next_candidates = (frozenset(x) for x in combinations(items, length))

    # Return all the candidates if the length of the next candidates is 2
    # because their subsets are the same as items.
    if length < 3:
        return list(tmp_next_candidates)

    # Filter candidates that all of their subsets are
    # in the previous candidates.
    next_candidates = [
        candidate for candidate in tmp_next_candidates
        if all(
            True if frozenset(x) in prev_candidates else False
            for x in combinations(candidate, length - 1))
    ]
    return next_candidates


def gen_support_records(transaction_manager, min_support, **kwargs):
    """
    Returns a generator of support records with given transactions.
    Arguments:
        transaction_manager -- Transactions as a TransactionManager instance.
        min_support -- A minimum support (float).
    Keyword arguments:
        max_length -- The maximum length of relations (integer).
    """
    # Parse arguments.
    max_length = kwargs.get('max_length')
    rhs_filter = kwargs.get('rhs_filter', None)

    # For testing.
    _create_next_candidates = kwargs.get(
        '_create_next_candidates', create_next_candidates)

    # Process.
    candidates = transaction_manager.initial_candidates()
    length = 1
    while candidates:
        relations = set()
        for relation_candidate in candidates:
            support = transaction_manager.calc_support(relation_candidate)
            if support < min_support:
                continue
            if rhs_filter and length > 1:
                has_filter = False
                for item in relation_candidate:
                    if rhs_filter in item:
                        has_filter = True
                    break
                if not has_filter:
                    continue
            candidate_set = frozenset(relation_candidate)
            relations.add(candidate_set)
            yield SupportRecord(candidate_set, support)
        length += 1
        if max_length and length > max_length:
            break
        candidates = _create_next_candidates(relations, length)


def gen_ordered_statistics(transaction_manager, record, rhs_filter=None):
    """
    Returns a generator of ordered statistics as OrderedStatistic instances.
    Arguments:
        transaction_manager -- Transactions as a TransactionManager instance.
        record -- A support record as a SupportRecord instance.
    """
    items = record.items
    for combination_set in combinations(sorted(items), len(items) - 1):
        items_base = frozenset(combination_set)
        items_add = frozenset(items.difference(items_base))
        if rhs_filter and len(items_base) != 0:
            has_filter = False
            for item in items_add:
                if rhs_filter in item:
                    has_filter = True
                break
            if not has_filter:
                continue
        confidence = (
            record.support / transaction_manager.calc_support(items_base))
        lift = confidence / transaction_manager.calc_support(items_add)
        yield OrderedStatistic(
            frozenset(items_base), frozenset(items_add), confidence, lift)


def filter_ordered_statistics(ordered_statistics, **kwargs):
    """
    Filter OrderedStatistic objects.
    Arguments:
        ordered_statistics -- A OrderedStatistic iterable object.
    Keyword arguments:
        min_confidence -- The minimum confidence of relations (float).
        min_lift -- The minimum lift of relations (float).
    """
    min_confidence = kwargs.get('min_confidence', 0.0)
    min_lift = kwargs.get('min_lift', 0.0)
    for ordered_statistic in ordered_statistics:
        if ordered_statistic.confidence < min_confidence:
            continue
        if ordered_statistic.lift < min_lift:
            continue
        yield ordered_statistic


################################################################################
# API function.
################################################################################
def apriori(transactions, **kwargs):
    """
    Executes Apriori algorithm and returns a RelationRecord generator.
    Arguments:
        transactions -- A transaction iterable object
                        (eg. [['A', 'B'], ['B', 'C']]).
    Keyword arguments:
        min_support -- The minimum support of relations (float).
        min_confidence -- The minimum confidence of relations (float).
        min_lift -- The minimum lift of relations (float).
        max_length -- The maximum length of the relation (integer).
    """
    global global_num_transaction
    # Parse the arguments.
    min_support = kwargs.get('min_support', 0.1)
    min_confidence = kwargs.get('min_confidence', 0.0)
    min_lift = kwargs.get('min_lift', 0.0)
    max_length = kwargs.get('max_length', None)
    item_map = kwargs.get('item_map', None)
    rhs_filter = kwargs.get('rhs_filter', None)
    # Check arguments.
    if min_support <= 0:
        raise ValueError('minimum support must be > 0')

    # For testing.
    _gen_support_records = kwargs.get(
        '_gen_support_records', gen_support_records)
    _gen_ordered_statistics = kwargs.get(
        '_gen_ordered_statistics', gen_ordered_statistics)
    _filter_ordered_statistics = kwargs.get(
        '_filter_ordered_statistics', filter_ordered_statistics)

    # Calculate supports.
    transaction_manager = TransactionManager.create(transactions, item_map=item_map)
    print('num_transactions: ' + str(transaction_manager.num_transaction))
    global_num_transaction = transaction_manager.num_transaction
    support_records = _gen_support_records(
        transaction_manager, min_support, max_length=max_length, rhs_filter=rhs_filter)

    # Calculate ordered stats.
    for support_record in support_records:
        ordered_statistics = list(
            _filter_ordered_statistics(
                _gen_ordered_statistics(transaction_manager, support_record, rhs_filter=rhs_filter),
                min_confidence=min_confidence,
                min_lift=min_lift,
            )
        )
        if not ordered_statistics:
            continue
        yield RelationRecord(
            support_record.items, support_record.support, ordered_statistics)


################################################################################
# Application functions.
################################################################################
def parse_args(argv):
    """
    Parse commandline arguments.
    Arguments:
        argv -- An argument list without the program name.
    """
    output_funcs = {
        'json': dump_as_json,
        'tsv': dump_as_two_item_tsv,
        'tsvall': dump_as_tsv,
    }
    default_output_func_key = 'tsvall'

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v', '--version', action='version',
        version='%(prog)s {0}'.format(__version__))
    parser.add_argument(
        'input', metavar='inpath', nargs='*',
        help='Input transaction file (default: stdin).',
        type=argparse.FileType('r'), default=[sys.stdin])
    parser.add_argument(
        '-o', '--output', metavar='outpath',
        help='Output file (default: stdout).',
        type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument(
        '-l', '--max-length', metavar='int',
        help='Max length of relations (default: infinite).',
        type=int, default=None)
    parser.add_argument(
        '-s', '--min-support', metavar='float',
        help='Minimum support ratio (must be > 0, default: 0.1).',
        type=float, default=0.1)
    parser.add_argument(
        '-c', '--min-confidence', metavar='float',
        help='Minimum confidence (default: 0.5).',
        type=float, default=0.5)
    parser.add_argument(
        '-t', '--min-lift', metavar='float',
        help='Minimum lift (default: 0.0).',
        type=float, default=0.0)
    parser.add_argument(
        '-d', '--delimiter', metavar='str',
        help='Delimiter for items of transactions (default: tab).',
        type=str, default='\t')
    parser.add_argument(
        '-f', '--out-format', metavar='str',
        help='Output format ({0}; default: {1}).'.format(
            ', '.join(output_funcs.keys()), default_output_func_key),
        type=str, choices=output_funcs.keys(), default=default_output_func_key)
    #added by afshin
    parser.add_argument(
        '-im', '--item-map', metavar='str',
        help='if should map all events containing the given string into that string (e.g. ivr_3923 => ivr (default: None).',
        type=str, default=None)
    parser.add_argument(
        '-rhs', '--rhs-filter', metavar='str',
        help='If RHS of the rules should have a string (partially matched) (default: no rhs filter)',
        type=str, default=None)
    args = parser.parse_args(argv)

    args.output_func = output_funcs[args.out_format]
    return args


def load_transactions(input_file, **kwargs):
    """
    Load transactions and returns a generator for transactions.
    Arguments:
        input_file -- An input file.
    Keyword arguments:
        delimiter -- The delimiter of the transaction.
    """
    delimiter = kwargs.get('delimiter', '\t')
    for transaction in csv.reader(input_file, delimiter=delimiter):
        yield transaction if transaction else ['']


def dump_as_json(record, output_file, num_transaction=0):
    """
    Dump an relation record as a json value.
    Arguments:
        record -- A RelationRecord instance to dump.
        output_file -- A file to output.
    """
    def default_func(value):
        """
        Default conversion for JSON value.
        """
        if isinstance(value, frozenset):
            return sorted(value)
        raise TypeError(repr(value) + " is not JSON serializable")

    converted_record = record._replace(
        ordered_statistics=[x._asdict() for x in record.ordered_statistics])
    json.dump(
        converted_record._asdict(), output_file,
        default=default_func, ensure_ascii=False)
    output_file.write(os.linesep)


def dump_as_two_item_tsv(record, output_file, num_transaction=0):
    """
    Dump a relation record as TSV only for 2 item relations.
    Arguments:
        record -- A RelationRecord instance to dump.
        output_file -- A file to output.
    """
    for ordered_stats in record.ordered_statistics:
        if len(ordered_stats.items_base) != 1:
            continue
        if len(ordered_stats.items_add) != 1:
            continue
        output_file.write('{0}\t{1}\t{2:.8f}\t{3:.8f}\t{4:.8f}{5}'.format(
            list(ordered_stats.items_base)[0], list(ordered_stats.items_add)[0],
            record.support, ordered_stats.confidence, ordered_stats.lift,
            os.linesep))

def dump_as_tsv(record, output_file, num_transaction=0):
    """
    Dump a relation record as TSV for all relations.
    Arguments:
        record -- A RelationRecord instance to dump.
        output_file -- A file to output.
    """
    for ordered_stats in record.ordered_statistics:
        output_file.write('{0}\t{1}\t{2:.8f}\t{3:.0f}\t{4:.8f}\t{5:.8f}{6}'.format(
            '|'.join(list(ordered_stats.items_base)), '|'.join(list(ordered_stats.items_add)),
            record.support, record.support * num_transaction, ordered_stats.confidence, ordered_stats.lift,
            os.linesep))

def main(**kwargs):
    """
    Executes Apriori algorithm and print its result.
    """
    # For tests.
    _parse_args = kwargs.get('_parse_args', parse_args)
    _load_transactions = kwargs.get('_load_transactions', load_transactions)
    _apriori = kwargs.get('_apriori', apriori)

    args = _parse_args(sys.argv[1:])
    transactions = _load_transactions(
        chain(*args.input), delimiter=args.delimiter)
    result = _apriori(
        transactions,
        max_length=args.max_length,
        min_support=args.min_support,
        min_confidence=args.min_confidence,
        item_map=args.item_map,
        rhs_filter=args.rhs_filter)
    for record in result:
        args.output_func(record, args.output, num_transation=global_num_transaction)


if __name__ == '__main__':
    main()
