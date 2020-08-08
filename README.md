# virtualphone

This repository contains the code to make your phone become a virtual phone controlled by Telegram

### Basic concept ###

The basic concept of the tool is to build a virtual phone able to expose to your contacts a virtual phone able to filter in and out calls, or to redirect them to other secondary phones.

The whole system can easily be controlled through a dedicated Telegram bot and integrated with your contacts and calendar.

It is suggested to have a flat plan including multi-party calls plus free calls and texts.

### Supported modems ###

The system was tested with [Huawei E173](https://consumer.huawei.com/en/routers/e3372/specs/) modem.

### Behavior ###

Each call between you (`A`) and the recipient/caller (`C`) is a multi-party call having the virtualphone (`B`) in the middle.

When receiving a call, from `C` to `B`, after answering the call, the system will put it on hold, hence initiate a new call with `A`.
As soon as `A` answers the incoming call from `B`, calls are joined, hence allowing `A` and `C` to communicate.

Similarly, when a new call is requested (through the `/call` command sent through Telegram), `B` initiates a new call with `A`.
As soon as `A` answers the incoming call from `B`, the system will put it on hold, hence initiate a new call with `C`.
As soon as `C` answers the incoming call from `B`, calls are joined, hence allowing `A` and `C` to communicate.

In addition, incoming calls and SMS are notified through Telegram.

### Installation ###

1. First, you need to create a Telegram bot: talk with the [BotFather](https://t.me/botfather) and ask it for a bot (and its respective token)
2. Then, you need to set the `BOT_TOKEN` variable on the `virtualphone.py` file, by adding the bot's token
3. The next part is to install in your server the requirements of the bot using `pip3 install -r requirements.txt`

### Configuration ###

First of all, you need to edit your `~/.bashrc` file to include the following environment variables:
```
export virtualphone_botowner='...' # use /getid to get your identifier
export virtualphone_bottoken='...' # use @BotFather Telegram bot to get it
export virtualphone_defaultcountrycode='+39' # the country code
export virtualphone_defaultmasterphone='+39340...' # the master phone number
export virtualphone_calendarurl='https://calendar.google.com/calendar/ical/...' # the url of your ical calendar
export virtualphone_temporaryownerpassword='your_password' # the password used to enable temporary owners
```

Group contacts are `vcf` files placed in the `contacts` folder: one file for each group, where the file name is the group name.
Alternatively, as soon as the bot is in execution, you can directly add group contacts files in `vcf` format by sending such files to the bot.

Optionally, you can configure `virtualphone.py` behavior by checking the configuration section at beginning of the file.

### Execution ###

Just run the software:
```
python3 virtualphone.py
```

If your SIM card has PIN enabled, you'll need to disable it (see [this post](https://developer.gemalto.com/threads/unlock-sim-require-pin-code) for further information).

### Available commands ###

* `/help` to show the help message
* `/getid` to get your chat id
* `/getowners` to get the chat ids of all current owners
* `/addtemporaryowner <password>` to add a third temporary owner to the bot (authentication is done by exchanging a clear text `<password>`)
* `/getcontactscount` to get the number of phone contacts registered
* `/verbose_on` to enable verbose mode
* `/verbose_off` to disable verbose mode
* `/command <c>` to send the AT command `<c>` to the serial port of the modem
* `/call <number> [<from>]` to initiate a call to the number `<number>` (optionally, from `<from>` number)
* `/close` to interrupt all existing calls
* `/sms <number> <text>` to text `<number>` with `<text>`
* `/setmasterphone <number>` to set the default master phone number
* `/getmasterphone` to get the default master phone number
* `/getmasterphonefromnumber` to get the master phone number from a given contact number `<number>`
* `/search <contact_name>` to look for a contact and related numbers from a given (even partial) name `<contact_name>`

### Temporary owners ###

It's possible to set up a temporary owner, if needed (this option can be disabled through a dedicated variable on `virtualphone.py`).
For instance, temporary owners may be needed in order to make calls when your master phone is unaccessible.
In this case, just use the `/addtemporaryowner` command as described above to enable it.

Once the temporary owner is not required anymore, just access your server and restart the service.

### Integration ###

The software provides integration with contacts and calendar.

#### Contacts integration ####

Contacts integration allows you to map each call numbers to registered contact names.
Also, each contact is considered inside of a contacts group, to match filters.

Contacts have to be sent as `vcf` files through Telegram, to the listening bot.
It is possible to quickly export `vcf` contacts through the macOS Address book app, by drag and drop of a group of contacts to a specific folder.
The name of the file (extension excluded) will be mapped to the name of the group.

#### Calendar integration ####

Calendar integration allows you to implement forwarding filters.

Just fill in the calendar, including events with title equal to the group name and the location equal to the forward phone number (the master phone to use).
A single event for each group has to be created.

Considering calendar integration, you have to set reccurring events with the preffered timelines, with name equal to the group name (as described above) and location as the master phone to use

In addition, it is possible to override group configurations, for specific contacts, by creating a contact event with title equal to the name of the contact.
Multiple names can be concatenated in this case.

### Known limits ###

Currently, when a call is received, the system automatically answers it and immediately puts the call on hold, to make a secondary call to the master phone.
This makes many persons (including call centers) hang up the phone.

In order to solve the issue, check the [automatic SMS answers section](https://github.com/auino/virtualphone#automatic-sms-answers).

How to enhance this? For instance, by adding a vocal waiting message telling the user the call is going to be forwarded and asking not to hang up the phone (apparently, interfacing with the secondary data channel is not easy as it may seem; community support needed).

### Automatic SMS answers ###

It is possible to set up the program to automatically send an SMS message to the caller.

Following automatic SMS answers are supported:
* on early call closure (see [known limits section](https://github.com/auino/virtualphone#known-limits))
* on calls that are not accepted

In order to configure automatic SMS answers, check `SMS_AUTOANSWER_*` variables in `virtualphone.py`.

### TODO ###

* Improve code readability
* Improve security
* Improve input checking
* Test with additional modems (community required)
* Support to voice inputs/outputs
* Support to (shared) blacklists
* Support to advanced logs silently sent as file every 24 hours
* Minimize timings (e.g. by exploiting the embedded event-based behavior)

### Contacts ###

You can find me on [Twitter](https://twitter.com) as [@auino](https://twitter.com/auino).
