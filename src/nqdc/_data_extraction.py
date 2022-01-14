from pathlib import Path
import logging
import csv
from typing import Generator, Dict, Union

from lxml import etree
import pandas as pd

from nqdc._coordinates import CoordinateExtractor
from nqdc._metadata import MetadataExtractor
from nqdc._text import TextExtractor
from nqdc._typing import PathLikeOrStr


_LOG = logging.getLogger(__name__)


def extract_data(
    articles_dir: PathLikeOrStr, articles_with_coords_only: bool = True
) -> Generator[Dict[str, pd.DataFrame], None, None]:
    articles_dir = Path(articles_dir)
    coord_extractor = CoordinateExtractor()
    metadata_extractor = MetadataExtractor()
    text_extractor = TextExtractor()
    n_articles, n_with_coords = 0, 0
    for subdir in sorted([f for f in articles_dir.glob("*") if f.is_dir()]):
        _LOG.info(f"Processing directory: {subdir.name}")
        for article_file in subdir.glob("pmcid_*.xml"):
            n_articles += 1
            article_data = _extract_article_data(
                article_file,
                metadata_extractor,
                text_extractor,
                coord_extractor,
            )
            if article_data is None:
                continue
            if article_data["coordinates"].shape[0]:
                n_with_coords += 1
            _LOG.info(
                f"Processed in total {n_articles} articles, {n_with_coords} "
                f"({n_with_coords / n_articles:.0%}) had coordinates"
            )
            if (
                article_data["coordinates"].shape[0]
                or not articles_with_coords_only
            ):
                yield article_data


def _extract_article_data(
    article_file: Path,
    metadata_extractor: MetadataExtractor,
    text_extractor: TextExtractor,
    coord_extractor: CoordinateExtractor,
) -> Union[None, Dict[str, pd.DataFrame]]:
    _LOG.debug(f"processing article: {article_file.name}")
    try:
        article = etree.parse(str(article_file))
    except Exception:
        _LOG.exception(f"Failed to parse {article_file}")
        return None
    metadata = metadata_extractor(article)
    text = text_extractor(article)
    text["pmcid"] = metadata["pmcid"]
    coords = coord_extractor(article)
    if coords.shape[0]:
        coords["pmcid"] = metadata["pmcid"]
    return {"metadata": metadata, "text": text, "coordinates": coords}


def extract_to_csv(
    articles_dir: PathLikeOrStr,
    output_dir: PathLikeOrStr,
    articles_with_coords_only: bool = False,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    metadata_csv = output_dir / "metadata.csv"
    text_csv = output_dir / "text.csv"
    coord_csv = output_dir / "coordinates.csv"
    with open(metadata_csv, "w", encoding="utf-8", newline="") as meta_f, open(
        text_csv, "w", encoding="utf-8", newline=""
    ) as text_f, open(coord_csv, "w", encoding="utf-8", newline="") as coord_f:
        metadata_writer = csv.DictWriter(meta_f, MetadataExtractor.fields)
        metadata_writer.writeheader()
        text_writer = csv.DictWriter(text_f, TextExtractor.fields)
        text_writer.writeheader()
        coord_writer = csv.DictWriter(coord_f, CoordinateExtractor.fields)
        coord_writer.writeheader()
        for article_data in extract_data(
            articles_dir, articles_with_coords_only=articles_with_coords_only
        ):
            metadata_writer.writerow(article_data["metadata"])
            text_writer.writerow(article_data["text"])
            coord_writer.writerows(
                article_data["coordinates"].to_dict(orient="records")
            )
