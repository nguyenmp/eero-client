This is a fork of https://github.com/343max/eero-client

It contains an additional script to take the networking metrics of devices and forward them to an InfluxDB cloud instance

Simple tests for some logic can be run with:
```
BUCKET="" ORG="" TOKEN="" URL="" python3 -m pytest forwarder.py
```

This was deployed onto the [hikariita server](https://github.com/nguyenmp/hikariita), that page contains more details on access.
```
scp -r eero-client/ root@159.65.102.173:~/
```

First you need to authenticate using the given client to get a token/cookie file.
```
python3 sample.py
```

You can do a one-shot forward like so:
```
BUCKET=03258913b97e3475 ORG=05bcb1a08937ee28 TOKEN="SECRET" URL="https://us-west-2-1.aws.cloud2.influxdata.com" python3 forwarder.py
```

Or you can loop it like so:

```
/bin/bash -c 'while true; do <the thing above>; sleep 5; done' &
```

If you're trying to 'redeploy' meaning delete existing runs, find PID via:
```bash
ps aux | grep python
killall <pid>
```

### Below is from the original README.txt

# unofficial barebone client lib for eero router (https://eero.com)

This is a very simple client lib to access information about your eero home network. I got this API by intercepting the traffic of the eero app.

Right now it support the following features:
- login/login verification
- user_token refreshing
- account (all information about an account, most importantly a list of your networks)
- networks (information about a particular network)
- devices (a list of devices connected to a network)
- reboot

The API is pretty nice and it should be kind of easy to extend it from here if you miss something. There are a lot of URLs in the response json that will help you explore the API further.

There is a sample client that you might use for your experiments. On first launch it will ask you for the phone number you used to create your eero account. Afterwards you've been asked for the verfication code that you got via SMS. From here on you are logged in - running the command again will dump a ton of information about your network(s).
