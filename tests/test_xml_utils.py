from chat_omni_digest.xml_utils import extract_media_fields, infer_kind


def test_extract_image_md5_from_xml():
    fields = extract_media_fields('<msg><img md5="0123456789abcdef0123456789abcdef"/></msg>')
    assert fields["md5"] == "0123456789abcdef0123456789abcdef"


def test_extract_file_md5_and_title():
    content = """
    <msg><appmsg><title>report.pdf</title><appattach>
    <filemd5>abcdefabcdefabcdefabcdefabcdefab</filemd5>
    <fileext>pdf</fileext>
    </appattach></appmsg></msg>
    """
    fields = extract_media_fields(content)
    assert fields["md5"] == "abcdefabcdefabcdefabcdefabcdefab"
    assert fields["title"] == "report.pdf"
    assert fields["fileext"] == "pdf"


def test_infer_kind():
    assert infer_kind("图片", "") == "image"
    assert infer_kind("视频", "") == "video"
    assert infer_kind("链接/文件", "<appattach/>") == "file"
