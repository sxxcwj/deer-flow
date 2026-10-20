/**
 * About page shown in workspace settings.
 * Inlined to avoid a raw-loader dependency
 * (Turbopack cannot resolve raw-loader for .md imports).
 */
import { APP_VERSION } from "@/version";

export const aboutMarkdown = `# 长伴咨询 [工作台 ${APP_VERSION}]

山西长伴人力资源有限公司。

> 每个高成长企业背后，都有长伴相随。

工作台用来承接组织、人才与激励方面的对话和项目。名称与材料由你自己填写，只保存在这台机器上。

## 联系

* [wangjian@cbrlzy.com](mailto:wangjian@cbrlzy.com)
* [132 3363 5522](tel:13233635522)

本工作台基于开源项目 [DeerFlow](https://github.com/bytedance/deer-flow) 搭建。
`;
