param exists bool

var defaultImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
var image = exists ? defaultImage : defaultImage

output containers array = [
  {
    image: image
  }
]
