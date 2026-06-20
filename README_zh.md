### Votingapp

这是一个为各种测试目的而构建的简单 API 服务。它最初是为了专门测试 AWS App Runner 而构建的，但也可以用于其他用途。此应用程序是 [Yelb](https://github.com/mreferre/yelb/) 的精简版本（并受其启发）。

该应用程序将"投票"存入并存储在 Amazon DynamoDB 表中。您可以通过 CURL（或类似工具）访问以下 4 个 API 来进行投票：
```
/api/outback
/api/bucadibeppo
/api/ihop
/api/chipotle
```
除了投票之外，您还可以通过 CURL（或类似工具）访问 `/api/getvotes` API 来查询状态。请注意，代码中有一个***实验性***功能，用于人为地消耗更多内存/CPU。可以通过访问 `/api/getheavyvotes` API 来使用此功能。人为负载的大小由两个变量决定（`MEMSTRESSFACTOR` 和 `CPUSTRESSFACTOR`，默认值为 `1`）。您可以通过将它们设置为 `0.1`（减少开销）或 `10`（增加开销）来调整负载量。

如果您访问服务的 `/` 路径，将提供各种可用 API 的摘要。此路径仅提供静态内容，不会测试 DynamoDB 连接。

以下是应用程序架构的高级示意图：

![votingapp-architecture](/images/votingapp-architecture.png)

### 如何设置应用程序

这是一个经典的 Python 应用程序。要将其与 AWS App Runner 一起使用，您可以提前构建镜像（提供了 `Dockerfile`）并将其推送到 ECR，或者您可以直接提供源代码。如果您使用 AWS App Runner 部署应用程序，仓库根目录包含用于配置运行时所需参数的 `apprunner.yaml` 文件。部署应用程序的前提条件是创建并初始化 DynamoDB 表并设置适当的权限。在 [preparation](/preparation) 文件夹中有相关说明和代码来完成此操作。

`apprunner.yaml` 文件已经过调整以启用 [X-Ray](https://aws.amazon.com/xray/) 集成，而无需对应用程序本身进行检测（有关如何启用此功能的更多信息，请参阅[此文档页面](https://docs.aws.amazon.com/apprunner/latest/dg/monitor-xray.html)）。如果您想激活此集成，请记得在可观测性配置部分中启用 `Tracing with AWS X-Ray`。

如果您想熟悉 App Runner 并获得有关如何使用源代码直接部署应用程序或使用现有 Docker 镜像部署应用程序的更详细的分步说明，请查看 [AWS App Runner Workshop](https://www.apprunnerworkshop.com/)。


#### AWS App Runner 控制台部署

首先，请查看此仓库中的 [preparation](/preparation) 文件夹，以创建 DynamoDB 表以及所需的各种角色和策略。此外，如果您选择从源代码部署，请将此仓库 fork 到您的 GitHub 账户。然后转到 AWS App Runner 控制台。

- 点击 `Create Service`
- 仓库类型：`Source code repository`
- 连接到您的 GitHub 账户并选择此仓库的 fork（使用 `main` 分支）
- 部署触发器：`Manual`
- 在构建设置中选择 `Use a configuration file`
- 为此服务命名
- 在 `Security` 部分（`Instance role`）中选择由 `prepare.sh` 脚本创建的 `votingapp-role` IAM 角色

最后一步很重要，因为它授予此 App Runner 服务访问 DynamoDB 表的权限。

请注意，`apprunner.yaml` 配置文件将 `DDB_AWS_REGION` 变量设置为 `us-west-2`。如果您的 DynamoDB 表位于其他区域（和/或如果您选择创建具有不同名称的表），请相应地更改/添加文件中的变量值。

#### AWS App Runner CLI 部署

与控制台部署类似，请首先查看此仓库中的 [preparation](/preparation) 文件夹，以创建 DynamoDB 表以及所需的各种角色和策略。此外，如果您选择从源代码部署，请将此仓库 fork 到您的 GitHub 账户。确保您已设置 AWS CLI 和适当的凭证。

要使用 AWS CLI 部署此应用程序，此仓库提供了一个 `apprunner_cli_input.json` 文件。它包含了您需要手动输入到控制台中的所有配置。

请记得替换 `apprunner_cli_input.json` 文件中的 `CONNECTION_ARN`、`GH_USER`、`ACCOUNT_ID` 和 `IAM_ROLE` 占位符。完成后，您只需运行以下命令：

```
aws apprunner create-service --cli-input-json file://apprunner_cli_input.json
```

#### 变量

- `DDB_AWS_REGION` 此变量是必需的，需要设置为 DynamoDB 表所在的区域。
- `DDB_TABLE_NAME` 此变量是可选的，包含 DynamoDB 表名称（默认值：`votingapp-restaurants`）
- `MEMSTRESSFACTOR` 和 `CPUSTRESSFACTOR` 是可选的，用于控制人为负载的行为（实验性功能）
- `OTEL_PYTHON_ID_GENERATOR` 和 `OTEL_PROPAGATORS` 是启用 X-Ray 集成所必需的
- `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS` 和 `OTEL_RESOURCE_ATTRIBUTES` 是可选的，与 X-Ray 集成相关

#### 使用其他服务和平台部署应用程序

此应用程序是为测试部署到 AWS App Runner 而创建的。但是，这是一个标准的 Python 应用程序，只要您遵循其架构和先决条件，就可以在任何其他环境中使用。该应用程序附带了 `requirements.txt` 文件和 `Dockerfile`。

#### 已知限制和待办事项

- `getheavyvotes` API 并未按预期工作，目前仍在开发中
- 该脚本理想情况下应转换为带有自定义资源的 CFN 模板以初始化 DDB 表
- 更理想的情况是，所有内容（App Runner 服务 + DDB 表）都可以/应该用 Copilot artifact 包装
- 一个用于投票和查询投票的简单 UI 正在开发中
- Flask 服务器未启用调试模式。要启用调试模式，请添加以下变量：`FLASK_ENV-development`（请注意此变量与 [OpenTelemetry 不兼容](https://github.com/open-telemetry/opentelemetry-python-contrib/issues/546)，因此在此问题修复之前 X-Ray 集成将无法工作）


#### 许可证

此应用程序基于 [MIT 许可证](./LICENSE) 提供。运行此应用程序所需的 Python 依赖项及其许可证如下：
```
Flask - BSD 许可证
Flask-Cors - MIT 许可证
Boto3 - Apache 许可证 2.0
Botocore - Apache 许可证 2.0
Simplejson - 学术自由许可证 (AFL)、MIT 许可证
```
