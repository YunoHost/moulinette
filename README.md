YunoHost CLI
============


Specifications
--------------


### User

    yunohost user list [-h] [--fields FIELDS [FIELDS ...]] [-o OFFSET]
                            [-f FILTER] [-l LIMIT]
    yunohost user create [-h] [-u USERNAME] [-l LASTNAME] [-f FIRSTNAME]
                              [-p PASSWORD] [-m MAIL]
    yunohost user delete [-h] [--purge] users [users ...]
    yunohost user update [-h] [-f FIRSTNAME]
                              [--add-mailalias MAIL [MAIL ...]] [-m MAIL]
                              [-l LASTNAME]
                              [--remove-mailforward MAIL [MAIL ...]]
                              [--remove-mailalias MAIL [MAIL ...]]
                              [--add-mailforward MAIL [MAIL ...]]
                              [-p PASSWORD]
                              user
    yunohost user info [-h] [-u USER] [-m MAIL]


### Domain

    yunohost domain list [-h] [-l LIMIT] [-o OFFSET] [-f FILTER]
    yunohost domain add [-h] [domain [domain ...]]
    yunohost domain remove [-h] [domain [domain ...]]
    yunohost domain info [-h] domain
    yunohost domain renewcert [-h] domain


### App

    yunohost app updatelist [-h] [-u URL]
    yunohost app list [-h] [--fields FIELDS [FIELDS ...]] [-o OFFSET]
                           [-f FILTER] [-l LIMIT]
    yunohost app install [-h] [-d DOMAIN] [--public] [-l LABEL] [-p PATH]
                              [--protected]
                              app
    yunohost app remove [-h] app [app ...]
    yunohost app upgrade [-h] [app [app ...]]
    yunohost app info [-h] app
    yunohost app addaccess [-h] [-u USER [USER ...]] app [app ...]
    yunohost app removeaccess [-h] [-u USER [USER ...]] app [app ...]


### Firewall

    yunohost firewall list [-h]
    yunohost firewall allow [-h] {UDP,TCP,Both} port name
    yunohost firewall disallow [-h] name


### Monitoring

    yunohost monitor disk [-h] [-m MOUNTPOINT] [-t] [-f] [-H]
    yunohost monitor network [-h] [-u] [-i] [-H]
    yunohost monitor system [-h] [-m] [-u] [-i] [-p] [-c] [-H]


### Services

    yunohost service status [-h] [NAME [NAME ...]]
    yunohost service start [-h] NAME [NAME ...]
    yunohost service stop [-h] NAME [NAME ...]
    yunohost service enable [-h] NAME [NAME ...]
    yunohost service disable [-h] NAME [NAME ...]


### Tools

    yunohost tools postinstall [-h] [-d DOMAIN] [-p PASSWORD]
    yunohost tools maindomain [-h] [-o OLD_DOMAIN] [-n NEW_DOMAIN]
    yunohost tools adminpw [-h] [-o OLD_PASSWORD] [-n NEW_PASSWORD]
    yunohost tools ldapinit [-h] [-d DOMAIN]


How to use "as is" ?
--------------------

The executable file is yunohost, for example:

    ./yunohost user create


Contribute / FAQ
----------------

*What a lovely idea !* :)

### Dafuq is dat moulinette ?
We decided to regroup all YunoHost related operations into a single program called "moulinette". This will allow us to entirely manipulate our YunoHost instances through a wonderful CLI. Additionally the web interface will just have to call the same "moulinette" functions. Magic power inside :p

### Important files
* `` yunohost `` File executed on function calling - i.e `` ./yunohost user create ``.
* `` action_map.yml `` Defines all CLI actions and links arguments.
* `` yunohost.py `` Contains all YunoHost functions likely to be shared between moulinette files. Also contains service connections classes (erk).
* `` yunohost_*.py `` Files containing action functions. `` * `` is the category: user, domain, firewall, etc.

### How to add a function ?
1. Check if the action is already in the `` action_map.yml `` file. If not, follow the file documentation to add it.
2. Also check if the file `` yunohost_category.py `` is created in the working tree. If not, just create it (you may take example of `` yunohost_user.py `` file).
3. Add your function `` category_action() `` in this file - i.e `` user_create() ``

**Note:** `` category_action() `` takes one parameter,`` args `` which contains the arguments passed to the command. Refers to `` action_map.yml `` documentation for more informations.

### Error handling
Moulinette has a unified way to handle errors. First, you need to import the ``YunoHostError`` exception:
`` from yunohost import YunoHostError ``

Then you need to raise errors like this:
`` raise YunoHostError(<ERROR CODE>, <MESSAGE>) ``

For example:
`` raise YunoHostError(125, _("Interrupted, user not created")) ``

**Note:** Standard error codes can be found in the ``YunoHostError`` class in `` yunohost.py `` file.

### Print results
Moulinette also have a unified way to print results. In fact we don't only print result for the CLI, but we also have to export the result in a JSON way.
Results are automatically printed OR exported, you don't have to print it yourself in the action's functions. Your function just need is to return results as a dictionary, for example:
`` return { 'Fullname' : 'Homer Simpson', 'Mail' : 'homer@simpson.org', 'Username' : 'hsimpson' } ``

### i18n
We will have to translate YunoHost, and we have already initialized i18n module in the moulinette. As a result, do not forget to put potentially translated strings into `` _() `` function. For example:
`` raise YunoHostError(125, _("Interrupted, user not created")) ``

### Git is pissing me off !
OK, this is the workflow !

**For gitlab:**
Development is handle with git branches and you have your own (i.e dev_beudbeud).
```
git clone git@dev.yunohost.org:moulinette.git
git checkout -b dev_beudbeud ``
git rebase origin/dev
```


Do your modifications, then :
```
git commit -am 'My commit message'
git pull origin dev (merge manually if conflicts)
git push origin dev_beudbeud
```

Then you could ask for a 'merge request' in gitlab.

**For github (here):**
Development is handle with forked repos and you have your own (i.e beudbeud/moulinette).
```
git clone https://github.com/beudbeud/moulinette.git ``
git checkout -b dev
git rebase origin/dev
```

Do your modifications, then:
```
git commit -am 'My commit message'
git remote add vanilla https://github.com/YunoHost/moulinette.git
git pull vanilla dev (merge manually if conflicts)
git push origin dev
```

Then you could ask for a 'pull request' in github.



