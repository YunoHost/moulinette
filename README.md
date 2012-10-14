YunoHost CLI
============


Specifications
--------------


### User

    yunohost user list [-h] [--fields FIELDS [FIELDS ...]] [-o OFFSET]
                            [-f FILTER] [-l LIMIT]
    yunohost user create [-h] [-u USERNAME] [-l LASTNAME] [-f FIRSTNAME]
                              [-p PASSWORD] [-m MAIL]
    yunohost user delete [-h] users [users ...]
    yunohost user update [-h] [-remove-mailalias MAIL [MAIL ...]]
                              [-add-mailalias MAIL [MAIL ...]] [-f FIRSTNAME]
                              [-m MAIL] [-l LASTNAME]
                              [--remove-mailforward MAIL [MAIL ...]]
                              [--add-mailforward MAIL [MAIL ...]]
                              [-cp PASSWORD]
                              user
    yunohost user info [-h] [-m MAIL] [-cn FULLNAME] [user]
    
    
### Domain
    
    yunohost domain list [-h] [-l LIMIT] [-o OFFSET] [-f FILTER]
    yunohost domain add [-h] domain
    yunohost domain remove [-h] domain [domain ...]
    yunohost domain info [-h] domain
    yunohost domain renewcert [-h] domain
    
    
### App 
    
    yunohost app list [-h] [--fields FIELDS [FIELDS ...]] [-o OFFSET]
                           [-f FILTER] [-l LIMIT]
    yunohost app install [-h] [-d DOMAIN] [--public] [-l LABEL] [-p PATH]
                              [--protected]
                              app [app ...]
    yunohost app remove [-h] app [app ...]
    yunohost app upgrade [-h] [app [app ...]]
    yunohost app info [-h] app
    yunohost app addaccess [-h] [-u USER [USER ...]] app [app ...]
    yunohost app removeaccess [-h] [-u USER [USER ...]] app [app ...]
    
    
### Repo
    
    yunohost repo list [-h] [-l LIMIT] [-o OFFSET] [-f FILTER]
    yunohost repo add [-h] [-n NAME] url
    yunohost repo remove [-h] repo
    yunohost repo update [-h]
    
    
### Firewall
    
    yunohost firewall list [-h]
    yunohost firewall allow [-h] {UDP,TCP,Both} port name
    yunohost firewall disallow [-h] name
    
    
### Monitoring
    
    yunohost monitor info #FIX
    
    
### Tools
    
    yunohost tools support #FIX
    


Contribute
----------


Only few functions are implemented yet. If you want to contribute, just pick one action above (i.e. 'yunohost app addaccess') and make the function (here 'app_addaccess()') into the right file (here 'yunohost_app.py').

If you need LDAP connections or openned configuration files, take a look at the connection documentation in the 'yunohost.py' file. 


Dev self-notes
--------------

* A big dictionary of categories/actions/arguments is translated to parsers and subparsers with argument handling (argparse python library)
* One single action function is called after the parsing, named like 'category_action()'
* Connection to LDAP and/or config file openning is made before the action function
* Parsed arguments and connection dictionary are the only parameters passed to the action function 
    category_action(args, connections)
* 'connections' is optionnal
* Connections are closed just before the sys.exit calling