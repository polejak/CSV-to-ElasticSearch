#!/usr/bin/python3

"""
DESCRIPTION
    Simple python script to import a csv into ElasticSearch. It can also update existing Elastic data if
    only parameter --id-column is provided

HOW IT WORKS
    The script creates an ElasticSearch API PUT request for
    each row in your CSV. It is similar to running an bulk insert by:

    $ curl -XPUT localhost:9200/_bulk -d '{index: "", type: ""}
                                         { data }'

    In both `json-struct` and `elastic-index` path, the script will
    insert your csv data by replacing the column name wrapped in '%'
    with the data for the given row. For example, `%id%` will be
    replaced with data from the `id` column of your CSV.

NOTES
    - CSV must have headers
    - insert elastic address (with port) as argument, it defaults to localhost:9200

EXAMPLES
    1. CREATE example:

    $ python csv_to_elastic.py \
        --elastic-address 'localhost:9200' \
        --csv-file input.csv \
        --elastic-index 'index' \
        --datetime-field=dateField \
        --json-struct '{
            "name" : "%name%",
            "major" : "%major%"
        }'

    CSV:

|  name  |      major       |
|--------|------------------|
|  Mike  |   Engineering    |
|  Erin  | Computer Science |


    2. CREATE/UPDATE example:

    $ python csv_to_elastic.py \
        --elastic-address 'localhost:9200' \
        --csv-file input.csv \
        --elastic-index 'index' \
        --datetime-field=dateField \
        --json-struct '{
            "name" : "%name%",
            "major" : "%major%"
        }'
        --id-column id
CSV:

|  id  |  name  |      major       |
|------|--------|------------------|
|   1  |  Mike  |   Engineering    |
|   2  |  Erin  | Computer Science |

"""

import argparse
import http.client
import os
import csv
import json
import dateutil.parser


def main(file_path, max_rows, elastic_index, json_struct, datetime_field,
         elastic_type, elastic_address, id_column, one_request_size):
    endpoint = '/_bulk'

    print("")
    print(" ----- CSV to ElasticSearch ----- ")
    print("Importing %s rows into `%s` from '%s'" % (max_rows, elastic_index, file_path))
    print("")

    count = 0
    headers = []
    headers_position = {}
    to_elastic_string = ""
    to_elastic_string_table = []
    with open(file_path, 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter=';', quotechar='"')
        for row in reader:
            if count == 0:
                for idx, col in enumerate(row):
                    headers.append(col)
                    headers_position[col] = idx
            elif max_rows is not None and count >= max_rows:
                print('Max rows imported - exit')
                break
            elif len(row[headers_position[datetime_field]]) == 0:    # Empty rows on the end of document
                print("Found empty rows at the end of document")
                break
            else:
                pos = 0
                if os.name == 'nt':
                    _data = json_struct.replace("^", '"')
                else:
                    _data = json_struct.replace("'", '"')
                for header in headers:
                    if header == datetime_field:
                        datetime_type = dateutil.parser.parse(row[pos])
                        _data = _data.replace('"%' + header + '%"', '"{:%Y-%m-%d %H:%M}"'.format(datetime_type))
                    else:
                        try:
                            int(row[pos])
                            _data = _data.replace('"%' + header + '%"', row[pos])
                        except ValueError:
                            _data = _data.replace('%' + header + '%', row[pos])
                    pos += 1
                # Send the request
                if id_column is not None:
                    index_row = {"index": {"_index": elastic_index,
                                           "_type": elastic_type,
                                           '_id': row[headers_position[id_column]]}}
                else:
                    index_row = {"index": {"_index": elastic_index, "_type": elastic_type}}
                json_string = json.dumps(index_row) + "\n" + _data + "\n"
                to_elastic_string += json_string
            count += 1

            if count % one_request_size == 0:
                to_elastic_string_table.append(to_elastic_string)
                to_elastic_string = ''

    if len(to_elastic_string) > 0:
        to_elastic_string_table.append(to_elastic_string)

    print('Reached end of CSV - sending to Elastic')

    connection = http.client.HTTPConnection(elastic_address)
    for data_chunk in to_elastic_string_table:
        connection.request('POST', url=endpoint, body=data_chunk)
        response = connection.getresponse()
        print("Returned status code:", response.status)
        request_response_body = response.read()
    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CSV to ElasticSearch.')

    parser.add_argument('--elastic-address',
                        required=False,
                        type=str,
                        default='localhost:9200',
                        help='Your elasticsearch endpoint address')
    parser.add_argument('--csv-file',
                        required=True,
                        type=str,
                        help='path to csv to import')
    parser.add_argument('--json-struct',
                        required=True,
                        type=str,
                        help='json to be inserted')
    parser.add_argument('--elastic-index',
                        required=True,
                        type=str,
                        help='elastic index you want to put data in')
    parser.add_argument('--elastic-type',
                        required=False,
                        type=str,
                        default='test_type',
                        help='Your entry type for elastic')
    parser.add_argument('--max-rows',
                        type=int,
                        default=None,
                        help='max rows to import')
    parser.add_argument('--datetime-field',
                        type=str,
                        help='datetime field for elastic')
    parser.add_argument('--id-column',
                        type=str,
                        default=None,
                        help='If you want to have index and you have it in csv, this the argument to point to it')
    parser.add_argument('--one-request-limit',
                        type=int,
                        required=False,
                        default=5000,
                        help='Amount of rows to insert with one request')

    parsed_args = parser.parse_args()

    main(file_path=parsed_args.csv_file, json_struct=parsed_args.json_struct,
         elastic_index=parsed_args.elastic_index, elastic_type=parsed_args.elastic_type,
         datetime_field=parsed_args.datetime_field, max_rows=parsed_args.max_rows,
         elastic_address=parsed_args.elastic_address, id_column=parsed_args.id_column,
         one_request_size=parsed_args.one_request_limit)
