PCH_RE = re.compile('\.[^\.]+$')
def find_pch(image_filename):
    return re.sub(PCH_RE, '.pch', image_filename)

def copy_animation_file(pch, image_filename):
    pass
