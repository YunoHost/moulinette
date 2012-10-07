# -*- coding: utf-8 -*-

""" Colored status messages """
error       = "\033[31m\033[1m" + _("Error:") + "\033[m "       # Red
interrupt   = "\033[31m\033[1m" + _("Interrupt:") + "\033[m "   # Red
notice      = "\033[34m\033[1m" + _("Notice:") + "\033[m "      # Cyan
success     = "\033[32m\033[1m" + _("Success:") + "\033[m "     # Green


""" Error codes """
EACCES          = 13  # Permission denied
EEXIST          = 17  # Exists
EINVAL          = 22  # Invalid argument
EUSERS          = 87  # Too many users
ECONNREFUSED    = 111 # Connection refused
EDQUOTA         = 122 # Quota exceeded
ECANCELED       = 125 # Operation Canceled
ENOTFOUND       = 167 # Not found
EUNDEFINED      = 168 # Undefined
ELDAP           = 169 # LDAP operation error
