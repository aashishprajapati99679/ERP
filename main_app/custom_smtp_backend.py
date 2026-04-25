import ssl
from django.core.mail.backends.smtp import EmailBackend as SmtpEmailBackend

class EmailBackend(SmtpEmailBackend):
    def open(self):
        """
        Ensure an open connection to the email server. Return whether or not a
        new connection was required (True or False) or None if an exception
        passed silently.
        """
        if self.connection:
            # Nothing to do if the connection is already open.
            return False

        from django.core.mail.utils import DNS_NAME
        connection_params = {'local_hostname': DNS_NAME.get_fqdn()}
        if self.timeout is not None:
            connection_params['timeout'] = self.timeout
            
        # Removed keyfile and certfile from connection_params for use_ssl
        # since Python 3.12 no longer supports them in smtplib.SMTP_SSL
        if self.use_ssl:
            context = ssl.create_default_context()
            connection_params['context'] = context

        try:
            self.connection = self.connection_class(self.host, self.port, **connection_params)

            # TLS/SSL are mutually exclusive, so only attempt TLS over
            # non-secure connections.
            if not self.use_ssl and self.use_tls:
                # Removed keyfile and certfile kwargs since Python 3.12+ removes them
                context = ssl.create_default_context()
                self.connection.starttls(context=context)
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except OSError:
            if not self.fail_silently:
                raise
