# -*- coding: utf-8 -*-
from src.utils.contract_types import (
    canonical_contract_type_key,
    infer_contract_type_from_xml,
    prettify_contract_type_name,
)


def test_infer_builtin_contract_type_from_xml_title():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <contract>
        <clauses>
            <clause id="1">
                <title>ДОГОВОР ПОСТАВКИ № 15</title>
                <content>
                    <paragraph>Поставщик обязуется поставить товар.</paragraph>
                </content>
            </clause>
        </clauses>
    </contract>
    """

    assert infer_contract_type_from_xml(xml) == "supply"


def test_infer_custom_contract_type_from_xml_title():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <contract>
        <clauses>
            <clause id="1">
                <title>Соглашение об урегулировании спора № 7</title>
                <content>
                    <paragraph>Стороны договорились урегулировать спор мирным путем.</paragraph>
                </content>
            </clause>
        </clauses>
    </contract>
    """

    assert infer_contract_type_from_xml(xml) == "Соглашение об урегулировании спора"


def test_canonical_key_dedupes_builtin_code_and_name():
    assert canonical_contract_type_key("supply") == canonical_contract_type_key("Договор поставки")


def test_prettify_unknown_dynamic_type():
    assert prettify_contract_type_name("settlement_agreement") == "Settlement agreement"


def test_infer_contract_type_from_filename_strips_hash_suffix():
    assert infer_contract_type_from_xml(
        "",
        file_name="Соглашение_урегулирование_клиника_81de19e6.docx",
    ) == "Соглашение урегулирование клиника"
