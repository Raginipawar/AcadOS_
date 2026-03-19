import zipfile
import xml.etree.ElementTree as ET
import sys

def read_docx(path):
    try:
        with zipfile.ZipFile(path) as docx:
            xml_content = docx.read('word/document.xml')
        tree = ET.XML(xml_content)
        # The namespace for Word XML
        word_ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        texts = []
        for p in tree.iter(word_ns + 'p'):
            texts.append(''.join(node.text for node in p.iter(word_ns + 't') if node.text))
        return '\n'.join(texts)
    except Exception as e:
        return str(e)

if __name__ == '__main__':
    print(read_docx(sys.argv[1]))
