# 异步数据导出的门户协议

项目保存供方接口协议、演练数据与回环地址服务。所有示例记录均使用本机演练资源，不连接实际供应平台。

运行环境为 Python 3.10 或以上，仅使用标准库。

```sh
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m src.source --port 8765
```

前两条命令分别检查供方源协议行为及语法；第三条启动本机服务，使用 Ctrl+C 结束。

GET /session 返回 csrf 并设置 sid Cookie。POST /exports 接受JSON表单，Cookie和X-CSRF-Token共同验证。GET /exports?client_ref=...查询；GET /jobs/job-1轮询；POST /jobs/job-1/refresh刷新链接；GET /download领取。POST /__control 可设置 lose_submit_response、sessions={}、job_status、link_expired。申请计数等于 /__state 中 jobs 数量。

GET /__state 可查看当前演练状态与已收到的请求。POST /__control 接受JSON，修改该服务实例的演练状态；此入口只用于本机供方模拟，不属于生产接口。服务端状态不跨进程保留。

src/source.py 是供方源实现；fixtures/source.json 保存协议示例数据；tests/test_source.py 检查供方源自身的响应。
