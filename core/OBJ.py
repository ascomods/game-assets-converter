class OBJ:
    supported_data = [
        'positions',
    #   'normals',
        'uvs'
    ]

    def __init__(self):
        self.data = {
            'positions': [],
        #    'normals': [],
            'uvs': []
        }

    def load(self, path):
        stream = open(path + 'data.obj', 'r')
        lines = stream.readlines()
        
        data = [x.split()[1:] for x in lines if x.startswith('v ')]
        [x.append('1.0') for x in data if len(x) == 3]
        data = [tuple(x) for x in data]

        self.data['positions'].append(
            {'data': data}
        )

        #data = [x.split()[1:] for x in lines if x.startswith('vn ')]
        #[x.append('0.0') for x in data if len(x) == 3]
        #data = [tuple(x) for x in data]

        #self.data['normals'].append(
        #    {'data': data}
        #)
        
        self.data['uvs'].append(
            {'data': [tuple(x.split()[1:]) for x in lines if x.startswith('vt ')]}
        )

    def save(self, path):
        stream = open(path + 'data.obj', 'w')
        stream.write("o Object\n")
        
        for vtx in self.data['positions'][0]['data']:
            stream.write(f"v {vtx[0]} {vtx[1]} {vtx[2]} {vtx[3]}\n")
        
        #for norm in self.data['normals'][0]['data']:
        #    stream.write(f"vn {norm[0]} {norm[1]} {norm[2]} {norm[3]}\n")
        
        for uvs in self.data['uvs'][0]['data']:
            stream.write(f"vt {uvs[0]} {uvs[1]}\n")
        
        flip = True

        for i in range(1, len(self.data['positions'][0]['data']) - 1):
            if flip:
                stream.write(f"f {i}/{i} {i+1}/{i+1} {i+2}/{i+2}\n")
            else:
                stream.write(f"f {i}/{i} {i+2}/{i+2} {i+1}/{i+1}\n")
            flip = not flip