# Security reporting

Please use GitHub private vulnerability reporting for security issues when
available, or contact the maintainer through the existing TerraLink project.
Do not publish credentials or private input data in an issue.

The standalone service is an experimental self-hosting implementation. Its default
bind is loopback. Upload execution and timeouts use subprocess isolation, but
public hosting also needs host-level resource limits, maintained geospatial
libraries, appropriate authentication where required, and a retention policy.
