'''Forwards device network data from my eero router to an InfluxDB
bucket for metrics and analyzing usage and debugging high usage'''


# Based on https://docs.influxdata.com/influxdb/v2.0/tools/client-libraries/python/
# $ python3.8
import logging
import os


# Configure and test logging real quick
logger = logging.getLogger()
format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s#%(funcName)s@%(lineno)s - %(message)s'
logging.basicConfig(format=format, level=logging.DEBUG)
logger.debug('Hello World')


BUCKET = os.environ['BUCKET']
ORG = os.environ['ORG']
TOKEN = os.environ['TOKEN']
URL = os.environ['URL']


def get_devices():
    logger.info('Getting devices')
    import subprocess
    import json
    output = subprocess.check_output(['python3.8', 'sample.py', 'devices'])
    logger.info('Parsing results')
    devices = json.loads(output)
    return devices


def as_payload(device):
    '''tags vs fields is based on
    https://docs.influxdata.com/influxdb/v1.8/concepts/schema_and_data_layout/#encode-meta-data-in-tags'''
    usage = device['usage'] or {}
    device_tags = [
        "url",
        "mac",
        "ip",
        "manufacturer",
        "nickname",
        "hostname",
        "device_type",
        "connected",
        "connection_type",
    ]
    tags = {
        tag: device[tag]  # I don't think influx can really handle null or None
        for tag in device_tags
        if device[tag] is not None
    }
    tags["source_location"] = device['source']['location']
    tags["interface_frequency"] = device['interface']['frequency'] or "0"
    tags["name"] = device['nickname'] or device['hostname'] or device['manufacturer'] or 'Unknown Device'  # hostname is automated, nickname is manual override

    return {
        "measurement": "devices",
        "tags": tags,
        "fields": {
            "usage_down_mbps": usage.get('down_mbps', 0),  # usage may be null when not connected
            "usage_up_mbps": usage.get('up_mbps', 0)  # usage may be null when not connected
        },
    }


ESCAPE_TAG_KEY = ESCAPE_TAG_VALUE = ESCAPE_FIELD_KEY = '(,|=| )'  # Commas, equals, spaces
ESCAPE_MEASUREMENTS = '(,| )'  # commas, spaces
ESCAPE_FIELD_VALUE = r'("|\\)'  # double quotes, backslash but only if strings

def escape(string, pattern):
    '''https://docs.influxdata.com/influxdb/v1.8/write_protocols/line_protocol_tutorial/#special-characters-and-keywords'''
    if isinstance(string, bool):
        import json
        return json.dumps(string)

    if isinstance(string, float):
        return '{:f}'.format(string)
    if isinstance(string, int):
        return string

    import re
    def repl(match):
        return '\\' + match.group(1)
    result = re.sub(pattern, repl, string)

    if pattern is ESCAPE_FIELD_VALUE:
        # Do double quote field values that are strings.
        # https://docs.influxdata.com/influxdb/v1.8/write_protocols/line_protocol_tutorial/#special-characters-and-keywords
        return '"{}"'.format(result)
    else:
        return result


def format_line(measurement, fields, tags, timestamp=None):
    '''https://docs.influxdata.com/influxdb/v1.8/write_protocols/line_protocol_tutorial/'''
    # Note: If there are no tags, the measurement has no comma after it
    # i.e. tags are preceeded by a comma
    formatted_tags = ''.join([
        ',{}={}'.format(escape(tag, ESCAPE_TAG_KEY), escape(value, ESCAPE_TAG_VALUE))
        for tag, value in sorted(tags.items())  # official tutorial recommends sorting tags by keys
    ])

    # commas separate fields, but is preceeded by whitespace
    formatted_fields = ','.join([
        '{}={}'.format(escape(field, ESCAPE_FIELD_KEY), escape(value, ESCAPE_FIELD_VALUE))
        for field, value in fields.items()
    ])

    line = '{}{} {}'.format(escape(measurement, ESCAPE_MEASUREMENTS), formatted_tags, formatted_fields)

    if timestamp:
        line += ' {}'.format(timestamp)

    logger.debug('Line generated: %s', line)
    return line


def write_stuff(devices):
    '''https://docs.influxdata.com/influxdb/v2.0/write-data/developer-tools/api/

    Since we are batching points together, we can just rely on the server's
    local timestamp.  If we were not batching, we would want to use the same
    timestamp across a single set of points generated.  Generating points can
    take a long time...

    curl -XPOST "https://us-west-2-1.aws.cloud2.influxdata.com/api/v2/write?org=YOUR_ORG&bucket=YOUR_BUCKET&precision=s" \
    --header "Authorization: Token YOURAUTHTOKEN" \
    --data-raw "
    mem,host=host1 used_percent=23.43234543 1556896326
    mem,host=host2 used_percent=26.81522361 1556896326
    mem,host=host1 used_percent=22.52984738 1556896336
    mem,host=host2 used_percent=27.18294630 1556896336
    "
    '''
    endpoint = '/api/v2/write'
    url = URL + endpoint
    query = {
        'org': ORG,
        'bucket': BUCKET,
    }
    headers = {
        "Authorization": "Token {}".format(TOKEN),
    }
    payloads = [as_payload(device) for device in devices]
    data = '\n'.join([
        format_line(
            measurement=payload['measurement'],
            fields=payload['fields'],
            tags=payload['tags'],
        )
        for payload in payloads
    ])
    import requests
    response = requests.post(url, params=query, headers=headers, data=data)
    response.raise_for_status()


def main():
    devices = get_devices()
    write_stuff(devices)


import pytest
@pytest.mark.parametrize("measurement,tags,fields,timestamp,expected_output", [
    ("weather", {'location': 'us-midwest'}, {'temperature': 82}, 1465839830100400200, 'weather,location=us-midwest temperature=82 1465839830100400200'),
    ("weather", {'location': 'us-midwest', 'season': 'summer'}, {'temperature': 82}, 1465839830100400200, 'weather,location=us-midwest,season=summer temperature=82 1465839830100400200'),
    ("weather", {}, {'temperature': 82}, 1465839830100400200, 'weather temperature=82 1465839830100400200'),
    ("weather", {'location': 'us-midwest'}, {'temperature': 82, 'humidity': 71}, 1465839830100400200, 'weather,location=us-midwest temperature=82,humidity=71 1465839830100400200'),
    ("weather", {'location': 'us-midwest'}, {'temperature': 82}, None, 'weather,location=us-midwest temperature=82'),
    ("weather", {'location': 'us-midwest'}, {'temperature': "too warm"}, 1465839830100400200, 'weather,location=us-midwest temperature="too warm" 1465839830100400200'),
    ("weather", {'location': 'us-midwest'}, {'too_hot': True}, 1465839830100400200, 'weather,location=us-midwest too_hot=true 1465839830100400200'),
    ("weather", {'location': 'us,midwest'}, {'temperature': 82}, 1465839830100400200, r'weather,location=us\,midwest temperature=82 1465839830100400200'),
    ("weather", {'location': 'us-midwest'}, {'temp=rature': 82}, 1465839830100400200, r'weather,location=us-midwest temp\=rature=82 1465839830100400200'),
    ("weather", {'location place': 'us-midwest'}, {'temperature': 82}, 1465839830100400200, r'weather,location\ place=us-midwest temperature=82 1465839830100400200'),
    ("wea,ther", {'location': 'us-midwest'}, {'temperature': 82}, 1465839830100400200, r'wea\,ther,location=us-midwest temperature=82 1465839830100400200'),
    ("wea ther", {'location': 'us-midwest'}, {'temperature': 82}, 1465839830100400200, r'wea\ ther,location=us-midwest temperature=82 1465839830100400200'),
    ("weather", {'location': 'us-midwest'}, {'temperature': 'too"hot"'}, 1465839830100400200, r'weather,location=us-midwest temperature="too\"hot\"" 1465839830100400200'),
    ("weather", {'location': 'us-midwest'}, {'temperature_str': 'too hot/cold'}, 1465839830100400201, r'weather,location=us-midwest temperature_str="too hot/cold" 1465839830100400201'),
    ("weather", {'location': 'us-midwest'}, {'temperature_str': 'too hot\\cold'}, 1465839830100400202, r'weather,location=us-midwest temperature_str="too hot\\cold" 1465839830100400202'),
    ("weather", {}, {'temperature': 1.00000e-05}, None, r'weather temperature=0.000010'),
])
def test_format_line(measurement, tags, fields, timestamp, expected_output):
    '''Taken from https://docs.influxdata.com/influxdb/v1.8/write_protocols/line_protocol_tutorial/'''
    assert format_line(measurement, fields, tags, timestamp) == expected_output


if __name__ == "__main__":
    main()
