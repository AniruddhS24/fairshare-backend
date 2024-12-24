import {
  Stack,
  StackProps,
  RemovalPolicy,
  CfnOutput,
  Duration,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import {
  aws_s3 as s3,
  aws_lambda as lambda,
  aws_apigateway,
  aws_dynamodb as dynamodb,
  aws_iam as iam,
} from "aws-cdk-lib";
import * as path from "path";
import * as dotenv from "dotenv";
dotenv.config();

export class FairshareBackendStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const receiptImageBucket = "fairshare-receipt-image-bucket";
    new s3.Bucket(this, "ReceiptImageBucket", {
      bucketName: receiptImageBucket,
      publicReadAccess: true,
      blockPublicAccess: {
        blockPublicAcls: false,
        blockPublicPolicy: false,
        ignorePublicAcls: false,
        restrictPublicBuckets: false,
      },
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      cors: [
        {
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.POST,
            s3.HttpMethods.PUT,
            s3.HttpMethods.DELETE,
          ],
          allowedOrigins: ["*"],
          allowedHeaders: ["*"],
        },
      ],
    });

    const receiptTable = new dynamodb.Table(this, "ReceiptTable", {
      partitionKey: { name: "id", type: dynamodb.AttributeType.STRING },
      tableName: "receipts",
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const itemsTable = new dynamodb.Table(this, "ItemsTable", {
      partitionKey: { name: "receipt_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "id", type: dynamodb.AttributeType.STRING },
      tableName: "items",
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const usersTable = new dynamodb.Table(this, "UsersTable", {
      partitionKey: { name: "id", type: dynamodb.AttributeType.STRING },
      tableName: "users",
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const rolesTable = new dynamodb.Table(this, "RolesTable", {
      partitionKey: { name: "receipt_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "user_id", type: dynamodb.AttributeType.STRING },
      tableName: "roles",
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const splitsTable = new dynamodb.Table(this, "SplitsTable", {
      partitionKey: { name: "receipt_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "id", type: dynamodb.AttributeType.STRING },
      tableName: "splits",
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const otpTable = new dynamodb.Table(this, "OTPTable", {
      partitionKey: { name: "phone", type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: "ttl",
      tableName: "otp",
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    // Add phone number GSI to the users table
    usersTable.addGlobalSecondaryIndex({
      indexName: "usersByPhoneNumber",
      partitionKey: { name: "phone", type: dynamodb.AttributeType.STRING },
    });

    // Add GSI to query splits by user
    splitsTable.addGlobalSecondaryIndex({
      indexName: "splitsByUser",
      partitionKey: { name: "receipt_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "user_id", type: dynamodb.AttributeType.STRING },
    });

    const api = new aws_apigateway.RestApi(this, "FairshareBackendAPI", {
      restApiName: "Fairshare Backend API",
      description: "This service handles the backend for the Fairshare app",
      defaultCorsPreflightOptions: {
        allowOrigins: aws_apigateway.Cors.ALL_ORIGINS,
        allowMethods: aws_apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          "Content-Type",
          "X-Amz-Date",
          "Authorization",
          "X-Api-Key",
          "X-Amz-Security-Token",
        ],
      },
    });

    const sharedRole = new iam.Role(this, "SharedLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonS3FullAccess"),
      ],
    });

    const ocrRole = new iam.Role(this, "OCRFunctionRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonS3FullAccess"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonTextractFullAccess"),
      ],
    });

    const middlewareLayer = new lambda.LayerVersion(this, "MiddlewareLayer", {
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../backend/middleware_layer"),
        {
          bundling: {
            image: lambda.Runtime.PYTHON_3_8.bundlingImage,
            command: [
              "bash",
              "-c",
              "pip install -r python/requirements.txt -t /asset-output/python && cp -au ./python /asset-output",
            ],
          },
        }
      ),
      compatibleRuntimes: [
        lambda.Runtime.PYTHON_3_8,
        lambda.Runtime.PYTHON_3_9,
      ],
    });

    const sharedEnvironment = {
      SECRET_JWT_KEY: process.env.SECRET_JWT_KEY || "",
    };

    const rootHandlerLambda = new lambda.Function(this, "HealthLambda", {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: "index.handler",
      code: lambda.Code.fromInline(
        `def handler(event, context): return {'statusCode': 200, 'body': 'Fairshare Backend'}`
      ),
      role: sharedRole,
    });

    const createJWTLambda = new lambda.Function(this, "JWTLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "token.create_token_lambda",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/token"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_8.bundlingImage,
          command: [
            "bash",
            "-c",
            "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output",
          ],
        },
      }),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const decodeJWTLambda = new lambda.Function(this, "GetJWTUserLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "token.get_user_lambda",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/token"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_8.bundlingImage,
          command: [
            "bash",
            "-c",
            "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output",
          ],
        },
      }),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const createOTPLambda = new lambda.Function(this, "CreateOTPLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "user.create_otp",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/user")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const verifyOTPLambda = new lambda.Function(this, "VerifyOTPLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "user.verify_otp",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/user")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const presignedUrlLambda = new lambda.Function(this, "PresignedUrlLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "upload.presigned_url",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/upload")),
      environment: {
        ...sharedEnvironment,
        BUCKET_NAME: receiptImageBucket,
      },
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const ocrLambda = new lambda.Function(this, "OcrLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "ocr.receipt_ocr",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/ocr")),
      environment: {
        ...sharedEnvironment,
        BUCKET_NAME: receiptImageBucket,
      },
      timeout: Duration.seconds(30),
      role: ocrRole,
      layers: [middlewareLayer],
    });

    const createReceiptLambda = new lambda.Function(this, "CreateReceipt", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "receipt.post",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/receipt")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const getReceiptByIdLambda = new lambda.Function(this, "GetReceiptByID", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "receipt.get_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/receipt")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const updateReceiptByIdLambda = new lambda.Function(
      this,
      "UpdateReceiptByID",
      {
        runtime: lambda.Runtime.PYTHON_3_8,
        handler: "receipt.update_by_id",
        code: lambda.Code.fromAsset(path.join(__dirname, "../backend/receipt")),
        environment: sharedEnvironment,
        timeout: Duration.seconds(30),
        role: sharedRole,
        layers: [middlewareLayer],
      }
    );

    const deleteReceiptByIdLambda = new lambda.Function(
      this,
      "DeleteReceiptByID",
      {
        runtime: lambda.Runtime.PYTHON_3_8,
        handler: "receipt.delete_by_id",
        code: lambda.Code.fromAsset(path.join(__dirname, "../backend/receipt")),
        environment: sharedEnvironment,
        timeout: Duration.seconds(30),
        role: sharedRole,
        layers: [middlewareLayer],
      }
    );

    const createItemLambda = new lambda.Function(this, "CreateItem", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "item.post",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/item")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const getItemsLambda = new lambda.Function(this, "GetItems", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "item.get",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/item")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const getItemByIdLambda = new lambda.Function(this, "GetItemById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "item.get_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/item")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const updateItemByIdLambda = new lambda.Function(this, "UpdateItemById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "item.update_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/item")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const deleteItemByIdLambda = new lambda.Function(this, "DeleteItemById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "item.delete_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/item")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const createSplitLambda = new lambda.Function(this, "CreateSplit", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "split.post",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/split")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const getSplitsLambda = new lambda.Function(this, "GetSplits", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "split.get",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/split")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const getSplitByIdLambda = new lambda.Function(this, "GetSplitById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "split.get_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/split")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const updateSplitByIdLambda = new lambda.Function(this, "UpdateSplitById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "split.update_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/split")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const deleteSplitByIdLambda = new lambda.Function(this, "DeleteSplitById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "split.delete_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/split")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const createUserLambda = new lambda.Function(this, "CreateUser", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "user.post",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/user")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const getUsersLambda = new lambda.Function(this, "GetUsers", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "user.get",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/user")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const getUserByIdLambda = new lambda.Function(this, "GetUserById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "user.get_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/user")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const updateUserByIdLambda = new lambda.Function(this, "UpdateUserById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "user.update_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/user")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const deleteUserByIdLambda = new lambda.Function(this, "DeleteUserById", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "user.delete_by_id",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/user")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const createPermissionLambda = new lambda.Function(
      this,
      "CreatePermission",
      {
        runtime: lambda.Runtime.PYTHON_3_8,
        handler: "role.post",
        code: lambda.Code.fromAsset(path.join(__dirname, "../backend/role")),
        environment: sharedEnvironment,
        timeout: Duration.seconds(30),
        role: sharedRole,
        layers: [middlewareLayer],
      }
    );

    const getPermissionLambda = new lambda.Function(this, "GetPermission", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: "role.get",
      code: lambda.Code.fromAsset(path.join(__dirname, "../backend/role")),
      environment: sharedEnvironment,
      timeout: Duration.seconds(30),
      role: sharedRole,
      layers: [middlewareLayer],
    });

    const getReceiptParticipantsLambda = new lambda.Function(
      this,
      "GetReceiptParticipants",
      {
        runtime: lambda.Runtime.PYTHON_3_8,
        handler: "role.get_receipt_participants",
        code: lambda.Code.fromAsset(path.join(__dirname, "../backend/role")),
        environment: sharedEnvironment,
        timeout: Duration.seconds(30),
        role: sharedRole,
        layers: [middlewareLayer],
      }
    );

    receiptTable.grantReadWriteData(createReceiptLambda);
    receiptTable.grantReadWriteData(getReceiptByIdLambda);
    receiptTable.grantReadWriteData(updateReceiptByIdLambda);
    receiptTable.grantReadWriteData(deleteReceiptByIdLambda);
    receiptTable.grantReadWriteData(ocrLambda);
    usersTable.grantReadWriteData(createUserLambda);
    usersTable.grantReadWriteData(getUsersLambda);
    usersTable.grantReadWriteData(getUserByIdLambda);
    usersTable.grantReadWriteData(updateUserByIdLambda);
    rolesTable.grantReadWriteData(createPermissionLambda);
    rolesTable.grantReadWriteData(getPermissionLambda);
    usersTable.grantReadWriteData(deleteUserByIdLambda);
    itemsTable.grantReadWriteData(createItemLambda);
    itemsTable.grantReadWriteData(getItemsLambda);
    itemsTable.grantReadWriteData(getItemByIdLambda);
    itemsTable.grantReadWriteData(updateItemByIdLambda);
    itemsTable.grantReadWriteData(deleteItemByIdLambda);
    itemsTable.grantReadWriteData(ocrLambda);
    splitsTable.grantReadWriteData(createSplitLambda);
    splitsTable.grantReadWriteData(getSplitsLambda);
    splitsTable.grantReadWriteData(getSplitByIdLambda);
    splitsTable.grantReadWriteData(updateSplitByIdLambda);
    splitsTable.grantReadWriteData(deleteSplitByIdLambda);
    otpTable.grantReadWriteData(createOTPLambda);
    otpTable.grantReadWriteData(verifyOTPLambda);

    api.root.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(rootHandlerLambda)
    );
    const uploadResource = api.root.addResource("upload");
    const ocrResource = api.root.addResource("ocr");
    const tokenResource = api.root.addResource("token");
    const generateOTPResource = api.root.addResource("otp_generate");
    const verifyOTPResource = api.root.addResource("otp_verify");
    const userResource = api.root.addResource("user");
    const userByIDResource = userResource.addResource("{user_id}");
    const receiptResource = api.root.addResource("receipt");
    const receiptByIDResource = receiptResource.addResource("{receipt_id}");
    const itemResource = receiptByIDResource.addResource("item");
    const itemByIDResource = itemResource.addResource("{item_id}");
    const splitResource = receiptByIDResource.addResource("split");
    const splitByIDResource = splitResource.addResource("{split_id}");
    const roleResource = receiptByIDResource.addResource("role");
    const receiptRolesResource =
      receiptByIDResource.addResource("participants");

    uploadResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(presignedUrlLambda)
    );
    ocrResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(ocrLambda)
    );
    tokenResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(createJWTLambda)
    );
    tokenResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(decodeJWTLambda)
    );
    generateOTPResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(createOTPLambda)
    );
    verifyOTPResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(verifyOTPLambda)
    );
    userResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(createUserLambda)
    );
    userResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getUsersLambda)
    );
    userByIDResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getUserByIdLambda)
    );
    userByIDResource.addMethod(
      "PUT",
      new aws_apigateway.LambdaIntegration(updateUserByIdLambda)
    );
    userByIDResource.addMethod(
      "DELETE",
      new aws_apigateway.LambdaIntegration(deleteUserByIdLambda)
    );
    receiptResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(createReceiptLambda)
    );
    receiptByIDResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getReceiptByIdLambda)
    );
    receiptByIDResource.addMethod(
      "PUT",
      new aws_apigateway.LambdaIntegration(updateReceiptByIdLambda)
    );
    receiptByIDResource.addMethod(
      "DELETE",
      new aws_apigateway.LambdaIntegration(deleteReceiptByIdLambda)
    );
    itemResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(createItemLambda)
    );
    itemResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getItemsLambda)
    );
    itemByIDResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getItemByIdLambda)
    );
    itemByIDResource.addMethod(
      "PUT",
      new aws_apigateway.LambdaIntegration(updateItemByIdLambda)
    );
    itemByIDResource.addMethod(
      "DELETE",
      new aws_apigateway.LambdaIntegration(deleteItemByIdLambda)
    );
    splitResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(createSplitLambda)
    );
    splitResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getSplitsLambda)
    );
    splitByIDResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getSplitByIdLambda)
    );
    splitByIDResource.addMethod(
      "PUT",
      new aws_apigateway.LambdaIntegration(updateSplitByIdLambda)
    );
    splitByIDResource.addMethod(
      "DELETE",
      new aws_apigateway.LambdaIntegration(deleteSplitByIdLambda)
    );
    roleResource.addMethod(
      "POST",
      new aws_apigateway.LambdaIntegration(createPermissionLambda)
    );
    roleResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getPermissionLambda)
    );
    receiptRolesResource.addMethod(
      "GET",
      new aws_apigateway.LambdaIntegration(getReceiptParticipantsLambda)
    );

    new CfnOutput(this, "ApiUrl", {
      value: api.url,
    });
  }
}
