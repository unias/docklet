class: center, middle

# HTTPS 支持

Author: [陈杰](mailto:1300012729@pku.edu.cn)  

Source Code: https://github.com/chenjiepk/docklet/tree/master

---

# Goal 

1. 支持HTTPS协议

2. 同时支持HTTP, 通过修改配置参数选择协议

---

# HTTPS 与 HTTP 比较

1. HTTP: TCP明文传输, 无法保证 机密性, 报文完整性, 端点鉴别 

2. HTTPS: SSL/TSL加密, 通过非对称加密发送密钥, 对称加密加密报文, 散列算法保证完整性

OpenSSL是实现SSL/TSL协议和大量加密算法的开源库, 实习中使用该工具本地生成证书用于测试.

## 


---

# 实现方案

1. Flask: Docklet的web server端使用Flask框架, 可以修改该部分代码实现HTTPS服务器

2. Configurable-http-proxy: Docklet中使用该代理转发请求至flask服务器, 可以配置命令参数实现将HTTP 请求转发为HTTP 请求, 参考[https->http](https://github.com/nodejitsu/node-http-proxy#using-https)


第2中方案较为简单，并且可以容易地选择协议。

`configurable-http-proxy  *  --ssl-key /path/to/key.pem --ssl-cert /path/to/cert.pem`



---


# 实验方案 续

问题: Flask中使用 `redirect` 跳转的地址仍然为HTTP协议, `url_for`并不能在代理和应用使用不同协议时生成正确的地址, 

1. `url_for(*args, _external=True, _scheme='https')`: 可行，但破坏了代码对HTTP兼容性 

2. 通常的做法是设置环境变量后对每个请求做一次协议变换, 参考[Fixing SCRIPT_NAME/url_scheme when behind reverse proxy](http://flask.pocoo.org/snippets/35/)

3. `app.wsgi_app = ProxyFix(app.wsgi_app)`: [werkzeug](http://werkzeug.pocoo.org/docs/0.11/contrib/fixers/) 库对该问题的修正,完美解决



---

# 结果和测试

源码修改汇总：

1. `conf/docklet.conf`中增加变量 `$PROXY_HTTPS="--ssl-key --ssl-cert"`,`bin/docklet-master` 中configurable-http-proxy命令增加参数  `$PROXY_HTTPS`

2. `web/web.py` 增加 `from werkzeug.contrib.fixers import ProxyFix    app.wsgi_app = ProxyFix(app.wsgi_app)`


测试结果:

1. `$PROXY_HTTPS` 未定义或者为空时, 采用HTTP 协议

2. `$PROXY_HTTPS` 正确指定证书文件时, 采用HTTPS 协议