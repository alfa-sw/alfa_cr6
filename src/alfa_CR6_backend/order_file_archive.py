# coding: utf-8

"""Preserve successfully imported order files outside the incoming folder."""

import logging
import os
import shutil


def _archive_dupont_order_file(path_to_file, archive_path):
    """Copy a successfully imported DuPont XML to the processed-file archive."""
    os.makedirs(archive_path, exist_ok=True)

    file_name = os.path.basename(path_to_file)
    destination = os.path.join(archive_path, file_name)
    stem, extension = os.path.splitext(file_name)
    copy_index = 1
    while os.path.exists(destination):
        destination = os.path.join(
            archive_path, f'{stem}_{copy_index}{extension}')
        copy_index += 1

    shutil.copy2(path_to_file, destination)
    logging.warning(
        "Archived DuPont order file from %s to %s",
        path_to_file,
        destination)
    return destination


def archive_order_file_if_needed(path_to_file, properties_list, data_path,
                                 archive_path=None):
    """Archive the source file when one of the created orders is DuPont XML."""
    is_dupont_xml = any(
        properties.get('meta', {}).get('header') == 'dupont_xml'
        for properties in properties_list)
    if not is_dupont_xml:
        return None

    if archive_path is None:
        archive_path = os.path.join(data_path, 'dupont_xml_archive')

    return _archive_dupont_order_file(path_to_file, archive_path)
