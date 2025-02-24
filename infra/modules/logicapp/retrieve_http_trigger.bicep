param logicAppName string
param triggerName string

var callbackUrl = listCallbackUrl(resourceId('Microsoft.Logic/workflows/triggers', logicAppName, triggerName), '2019-05-01').value
output url string = callbackUrl
