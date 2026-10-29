# Robot HTTPS certificate

Every robot serves `https://192.168.4.1` with this one self-signed certificate, so a phone that
accepts it once (or installs it) is fine with every robot. The private key is public on purpose: the
certificate is `CA:FALSE`, so it can't be used to sign anything else, and it only names 192.168.4.1.
HTTPS is here because browsers only allow the Gamepad API on secure pages.

It's valid for 825 days (Apple's limit for server certificates). Before it expires, make a new one
and release new firmware:

```sh
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout prvtkey.pem -out servercert.pem -days 825 -subj "/O=Columbia Gadget Works/CN=192.168.4.1" \
  -addext "subjectAltName=IP:192.168.4.1" -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature" -addext "extendedKeyUsage=serverAuth"
```
