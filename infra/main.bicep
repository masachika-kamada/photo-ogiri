@description('Short lowercase prefix used in resource names.')
param prefix string = 'photoogiri'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('PostgreSQL administrator login.')
param postgresAdminLogin string = 'photoogiriadmin'

@secure()
@description('PostgreSQL administrator password.')
param postgresAdminPassword string

var suffix = take(uniqueString(resourceGroup().id), 6)
var compactName = toLower('${take(prefix, 11)}${suffix}')

resource storage 'Microsoft.Storage/storageAccounts@2025-06-01' = {
  name: take('${compactName}store', 24)
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-06-01' = {
  parent: storage
  name: 'default'
}

resource submissions 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01' = {
  parent: blobService
  name: 'submissions'
  properties: { publicAccess: 'None' }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2025-06-01' = {
  parent: storage
  name: 'default'
}

resource scoreQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2025-06-01' = {
  parent: queueService
  name: 'score-jobs'
}

resource poisonQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2025-06-01' = {
  parent: queueService
  name: 'score-jobs-poison'
}

resource storageLifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2025-06-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'delete-submissions-after-7-days'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['submissions/']
            }
            actions: {
              baseBlob: {
                delete: { daysAfterModificationGreaterThan: 7 }
              }
            }
          }
        }
      ]
    }
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${compactName}-logs'
  location: location
  properties: { retentionInDays: 30 }
}

resource containerEnvironment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: '${compactName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: take('${compactName}acr', 50)
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' = {
  name: '${compactName}-pg'
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    version: '16'
    storage: { storageSizeGB: 32 }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
    authConfig: {
      activeDirectoryAuth: 'Disabled'
      passwordAuth: 'Enabled'
    }
  }
}

resource azureServicesFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-08-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: postgres
  name: 'photoogiri'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${take(registry.name, 40)}-identity'
  location: location
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, appIdentity.id, 'acr-pull')
  scope: registry
  properties: {
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource blobAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, appIdentity.id, 'blob-data')
  scope: storage
  properties: {
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

resource queueAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, appIdentity.id, 'queue-data')
  scope: storage
  properties: {
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
  }
}

output storageAccountName string = storage.name
output storageBlobUrl string = storage.properties.primaryEndpoints.blob
output storageQueueUrl string = storage.properties.primaryEndpoints.queue
output containerEnvironmentName string = containerEnvironment.name
output acrName string = registry.name
output acrLoginServer string = registry.properties.loginServer
output postgresServerName string = postgres.name
output postgresAdminLogin string = postgresAdminLogin
output appIdentityName string = appIdentity.name
output appIdentityClientId string = appIdentity.properties.clientId