#!/usr/bin/env python2.7
# requires:  https://pypi.python.org/pypi/http-parser
from twisted.internet import reactor, protocol, ssl
from twisted.python import log
from http_parser.pyparser import HttpParser
from WebClient import WebCheckFactory, JobFactory
from DNSclient import DNSclient
from Pingclient import PingProtocol

class MonitorCore(object):

    def __init__(self, params, jobs):
        self.params = params
        self.jobs = jobs
        self.ping = "/usr/bin/ping"
        self.ping_cnt = str(5)

    def get_job(self):
        factory = JobFactory(self.params, self.jobs)
        if self.params.get_scheme() == "https":
            ssl_obj = ssl.CertificateOptions()
            reactor.connectSSL(self.params.get_ip(), self.params.get_port(), factory, ssl_obj,\
                                            self.params.get_timeout())
        elif self.params.get_scheme() == "http":
            reactor.connectTCP(self.params.get_ip(), self.params.get_port(), factory, \
                    self.params.get_timeout())
        else:
            raise Exception("Unknown scheme:  %s" % self.params.get_scheme())
        # Keep looking for more work
        reactor.callLater(5, self.get_job)

    def dns_fail(self, job):
        # Do this if the DNS check failed
        jobid = job.get_job_id()
        print "DNS Failed for job %s! %s" % (jobid, failure)
        job.set_ip("fail")
        # Raise an exception to continue on the errback chain for the DNS deffered.
        # Returning here would go to the next callback in the chain, which will try
        # and ping the host.
        raise Exception("Fail Host")

    def post_job(self, job):
        job_id = job.get_job_id()
        factory = JobFactory(self.params, self.jobs, "put", job_id)
        reactor.connectTCP(self.params.get_sb_ip(), self.params.get_sb_port(), factory, \
                            self.params.get_timeout())

    def ping_fail(self, job):
        # Todo - add code to handle ping failure
        # Do this if the Ping check failed
        pass

    def ping(self, job):
        # Ping
        ipaddr = job.get_ip()
        pingobj = PingProtocol(ipaddr)
        ping_d = pingobj.getDeferred()
        ping_d.addCallback(self.check_services, job)
        ping_d.addErrback(self.ping_fail, job)
        reactor.spawnProcess(pingobj, self.ping, [self.ping, "-c", self.ping_cnt, ipaddr])

    def check_services(self, job):
        # Service walk
        for service in job.get_services():
            if service.has_auth:
                # TODO - write this code after the json is updated with service creds in SBE
                pass
            if "tcp" in service.get_proto():
                factory = None
                if service.get_port() == 80:
                    factory = WebCheckFactory(self.params, service)
                if factory:
                    reactor.connectTCP(job.get_ip(), service.get_port(), factory, self.params.get_timeout())
            elif "udp" in service.get_proto():
                # TODO - write the code to handle UDP checks
                pass
            else:
                raise Exception("Unknown protocol %s!" % service.get_proto())

    def start_job(self):
        # Get the next job started
        job = self.jobs.get_job()
        if job:
            # DNS
            dnsobj = DNSclient(job)
            # Execute the query
            query_d = dnsobj.query()
            # Handle a DNS failure - fail the host
            query_d.addErrback(self.dns_fail, job)
            # Handle a DNS success - move on to ping
            query_d.addCallback(self.ping, job)
            # Either the ping failed, or we continue from the DNS failure.
            query_d.addErrback(self.post_job, job)
        reactor.callLater(1, self.start_job)


if __name__=="__main__":
    # Testing with an artificial job file
    params = Parameters()
    jobs = Jobs
    monobj = MonitorCore(params, jobs)
    reactor.callLater(5, monobj.get_job)
    reactor.callLater(10, monobj.start_job)
    reactor.run()
