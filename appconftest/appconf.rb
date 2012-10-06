require 'yunohost/appconf'

class WordPress < Appconf
	
  homepage 'http://www.gnu.org/wget/'
  url 'http://ftp.gnu.org/wget-1.12.tar.gz'
  md5 '308a5476fc096a8a525d07279a6f6aa3'


  def preinstall
    system 'make install'
  end

  def upgrade
    system 'make install'
  end

  def db_upgrade
    system 'make install'
  end

  def remove
    system 'make install'
  end

  def backup
    system 'make install'
  end

  def restore
    system 'make install'
  end
end

