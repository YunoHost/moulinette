Under redaction
===============


YunoHost CLI
------------

### User

    yunohost user list --fields=fields,.. --filter=filter --limit=limit --offset=offset
    yunohost user add [fields=values...]
    yunohost user delete [users...]
    yunohost user update [user] --changepassword [oldpwd] [newpwd] | --mailforward [add/remove] [mails...]  | --    mailalias [add/remove] [mails...] | [fields=values...]
    yunohost user info [user]
    
    
### Domain
    
    yunohost domain list --filter=filter --limit=limit --offset=offset
    yunohost domain add [domain]
    yunohost domain delete [domains...]
    yunohost domain info [domain]
    yunohost domain renewcert [domain]
    
    
### App 
    
    yunohost app list --fields=fields,.. --filter=filter --limit=limit --offset=offset
    yunohost app install [apps...] --domain=domain --path=path --label=label --public --protected
    yunohost app remove [apps...]
    yunohost app upgrade [apps...]
    yunohost app info [app]
    yunohost app addaccess [apps...] --everyone | --users=users,..
    yunohost app removeaccess [apps...] --everyone | --users=users,..
    
    
### Repo
    
    yunohost repo list  --filter=filter --limit=limit --offset=offset
    yunohost repo add [url] --name=name
    yunohost repo remove [name/url]
    yunohost repo update
    
    
### Firewall
    
    yunohost firewall list
    yunohost firewall allow [port] [TCP/UDP/Both] [name]
    yunohost firewall disallow [name]
    
    
### Monitoring
    
    yunohost monitor
    
    
### Other
    
    yunohost paste
    yunohost support
    
    
    
YunoHost REST API
-----------------

Prefix: https://mydomain.org:6767
    
    /route
        METHOD  {params}
    
    
### User
    
    /user/list
        GET     {fields, filter, limit, offset}
    
    /user
        GET     {user, fields}
        POST    {fields, fieldsvalue}
        DELETE  {users}
        PUT     {user, fields}
    
    /user/changepassword
        PUT     {user, oldpwd, newpwd}
    
    /user/mailforward
        POST    {mails}
        DELETE  {mails}
    
    /user/mailalias
        POST    {mails}
        DELETE  {mails}
    
    
### Domain
    
    /domain/list
        GET     {filter, limit, offset}
    
    /domain
        GET     {domain}
        POST    {domain}
        DELETE  {domains}
    
    /domain/renewcert
        PUT     {domain}
    
    
### App

    /app/
    
    
    
YunoHost Web Views
------------------

### User
    
    /user/list
    /user/add
    /user/show/<user>
    /user/update/<user>
    /user/changepassword/<user>
    /user/mailforward/<user>
    /user/mailalias/<user>    