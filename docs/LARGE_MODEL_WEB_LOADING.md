# Large Model Web Loading P0

## 目标

当前 Scania 的问题不是“慢”，而是全量 Viewer JSON 会让浏览器无法完成加载。P0 的定义是：**禁止整车单体 payload，让首批几何可见，然后按分块渐进加载，并把网格结果持久缓存。**

## 架构边界

- STEP / XCAF / BRep：工程计算真值。
- View Derivative：浏览器消费的派生数据，不参与工程判定。
- three-cad-viewer：只负责 WebGL 场景和交互。

```
STEP -> XCAF/BRep --------------------> Geometry Check
              \
               -> ViewDerivativeStore -> manifest -> chunk cache -> Web streaming
```

## P0 API

- `GET /api/models/{key}/viewer/manifest?profile=preview`
- `GET /api/models/{key}/viewer/chunks/{chunk_id}?profile=preview`
- `GET /api/models/{key}/viewer/cache?profile=preview`
- `GET /api/models/{key}/inventory/summary`
- `GET /api/models/{key}/inventory/subshapes?path=...`

大模型不再使用全量 `/api/models/{key}/viewer` 作为默认加载链路。

## Viewer Profile

`preview`：粗网格、关闭边线，用于整车首屏。

`normal`：普通浏览。

`evidence`：局部证据，高质量并保留边线。

工程测量始终使用 OCCT BRep，不使用 LOD 网格作为判定依据。

## 缓存

`.cadcheck/cache/viewer/<source-sha>-<schema>-<profile>/`

缓存键包含 STEP SHA256、Derivative Schema 和 Tessellation Profile。相同源文件二次打开直接复用 chunk，不重复网格化。

## 前端原则

- 真进度：按已加载 Part / 总 Part 展示，不做虚假百分比。
- STEP/XCAF 内部没有可用细粒度回调时使用不定进度状态。
- 第一 chunk 到达即可旋转/缩放；后续 chunk 用 `viewer.addPart()` 增量加入。
- 低频功能放入“更多”：模型/数据、工程工具、证据/调试。
- Check Evidence 仍走局部对象，不依赖整车全部加载完成。

## 本地启动

```
./scripts/bootstrap.sh
./start.sh
```

`start.sh` 使用 `server.app_v2:app`，在原有工程 API 上叠加 streaming derivative API。

## P0 验收

1. Scania 不再请求/构造 1.56GB 单体 Viewer JSON。
2. 前端显示真实 chunk/part 加载进度。
3. 第一批几何到达后界面即可交互。
4. 后续 chunk 渐进加入，不刷新整页。
5. 同一 STEP 二次打开命中磁盘 mesh cache。
6. Inventory 默认只返回 leaf summary；subshape 按对象懒加载。
