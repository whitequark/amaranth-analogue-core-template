from pathlib import Path
from fractions import Fraction

import time
import json
import jsonschema
import tomli
import zipfile


ANALOGUE_TOML_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "analogue.toml",
    "type": "object",
    "required": ["metadata", "video"],
    "additionalProperties": False,
    "properties": {
        "metadata": {
            "type": "object",
            "required": ["platform", "core"],
            "additionalProperties": False,
            "properties": {
                "platform": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        # "id" is strictly required, name/manufacturer/year *can* be omitted but the defaults are bad
                        "required": ["id", "name", "manufacturer", "year"],
                        "properties": {
                            "id": {
                                "type": "string",
                                "pattern": "^[a-z0-9][a-z0-9_]*$",
                                "maxLength": 15
                            },
                            "category": {
                                "type": "string",
                                "maxLength": 31
                            },
                            "name": {
                                "type": "string",
                                "maxLength": 31
                            },
                            "manufacturer": {
                                "type": "string",
                                "maxLength": 31
                            },
                            "year": {
                                "type": "integer"
                            }
                        }
                    },
                    # Empty platform_ids core metadata key is permitted by the Analogue specification.
                    "minItems": 0,
                    "maxItems": 4
                },
                "core": {
                    "type": "object",
                    "additionalProperties": False,
                    # "author" and "name" are strictly required, version *can* be omitted but the default is bad
                    "required": ["author", "name", "version"],
                    "properties": {
                        "author": {
                            "type": "string",
                            "maxLength": 31
                        },
                        "name": {
                            "type": "string",
                            "maxLength": 31
                        },
                        "description": {
                            "type": "string",
                            "maxLength": 63
                        },
                        "description_long": {
                            "type": "string"
                        },
                        "url": {
                            "type": "string",
                            "format": "uri",
                            "maxLength": 63
                        },
                        "version": {
                            "type": "string",
                             # This is more restrictive than Analogue requires.
                            "pattern": "^(\d+).(\d+).(\d+)",
                            "maxLength": 31
                        },
                        "release_date": {
                            "type": "string",
                            "format": "date",
                            "minLength": 10,
                            "maxLength": 10
                        }
                    }
                }
            }
        },
        "core": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "sleep_supported": { # Defaults to False.
                    "type": "boolean"
                }
            }
        },
        "audio": {
            "type": "object",
            "additionalProperties": False,
        },
        "video": {
            "type": "object",
            "additionalProperties": False,
            "required": ["mode"],
            "properties": {
                "mode": {
                    "type": "array",
                    "items": {
                        "required": ["width", "height"],
                        "properties": {
                            "width": {
                                "type": "integer",
                                "minimum": 16,
                                "maximum": 800, # Additional restrictions apply when rotation in use.
                            },
                            "height": {
                                "type": "integer",
                                "minimum": 16,
                                "maximum": 720,
                            },
                            "pixel_width": {
                                "type": "integer",
                                "minimum": 1
                            },
                            "pixel_height": {
                                "type": "integer",
                                "minimum": 1
                            },
                            "rotation": {
                                "type": "integer",
                                "enum": [0, 90, 180, 270]
                            },
                            "mirror_horizontal": {
                                "type": "boolean"
                            },
                            "mirror_vertical": {
                                "type": "boolean"
                            },
                            "configuration": {
                                "type": "object"
                            }
                        },
                        "dependentRequired": {
                            "pixel_width": ["pixel_height"],
                            "pixel_height": ["pixel_width"],
                        }
                    }
                }
            }
        },
        "input": {
            "type": "object",
            "additionalProperties": False,
        },
        "interact": {
            "type": "object",
            "additionalProperties": False,
        },
        "data": {
            "type": "object",
            "additionalProperties": False,
        },
    }
}


class ValidationError(Exception):
    pass


class Metadata:
    def __init__(self, toml_filename: Path, core_names: list[str]):
        self.core_names = core_names
        with open(toml_filename, "rb") as f:
            self._data = tomli.load(f)
        try:
            jsonschema.validate(self._data, ANALOGUE_TOML_SCHEMA)
        except jsonschema.ValidationError as err:
            err_path = ".".join(map(str, err.path))
            raise ValidationError(f"Error in `{toml_filename}` at `{err_path}`: {err.message}")
    
    @property
    def _metadata_core(self):
        return self._data["metadata"]["core"]
    
    # Metadata queries.

    @property
    def author(self):
        return self._metadata_core["author"]

    @property
    def name(self):
        return self._metadata_core["name"]

    @property
    def version(self):
        return self._metadata_core["version"]
    
    @property
    def release_date(self):
        return self._metadata_core.get("release_date", time.strftime("%Y-%m-%d"))
    
    @property
    def video_modes(self):
        return self._data["video"]
    
    # Generated files.

    @property
    def platform_jsons(self):
        platform_jsons = {}
        for metadata_platform in self._data["metadata"]["platform"]:
            json_platform = {
                "name": metadata_platform["name"],
                "manufacturer": metadata_platform["manufacturer"],
                "year": metadata_platform["year"],
            }
            if "category" in metadata_platform: 
                json_platform["category"] = metadata_platform["category"]
            platform_jsons[metadata_platform["id"]] = {
                "platform": json_platform
            }
        return platform_jsons

    @property
    def core_directory(self):
        return f"Cores/{self.author}.{self.name}"
    
    @property
    def core_json(self):
        metadata_platforms = self._data["metadata"]["platform"]
        core = self._data.get("core", {})

        json_core_metadata = {
            "platform_ids": [
                metadata_platform["id"]
                for metadata_platform in metadata_platforms
            ],
            "author": self._metadata_core["author"],
            "shortname": self._metadata_core["name"],
            "version": self._metadata_core["version"],
            "date_release": self.release_date
        }
        if "description" in self._metadata_core:
            json_core_metadata["description"] = self._metadata_core["description"]
        if "url" in self._metadata_core:
            json_core_metadata["url"] = self._metadata_core["url"]
        return {
            "core": {
                "magic": "APF_VER_1",
                "metadata": json_core_metadata,
                "framework": {
                    "target_product": "Analogue Pocket",
                    "version_required": "1.1",
                    "sleep_supported": core.get("sleep_supported", False),
                    "dock": {
                        "supported": True, # Must be True.
                        "analog_output": False
                    },
                    "hardware": {
                        "link_port": False,
                        "cartridge_adapter": -1
                    }
                },
                "cores": [
                    {
                        "id": core_id, # Integer or hex string.
                        "name": core_name[:15], # Max 15 characters.
                        "filename": f"core_{core_id}.rbf_r" # Max 15 characters.
                    }
                    for core_id, core_name in enumerate(self.core_names)
                ]
            }
        }

    @property
    def info_txt(self) -> str:
        return self._data["metadata"]["core"].get("description_long", "")

    @property
    def variants_json(self):
        return {
            "variants": {
                "magic": "APF_VER_1",
                "variant_list": []
            }
        }

    @property
    def video_json(self):
        json_scaler_modes = []
        for video_mode in self._data.get("video").get("mode", []):
            aspect = (
                Fraction(video_mode["width"], video_mode["height"]) *
                Fraction(video_mode.get("pixel_width", 1), video_mode.get("pixel_height", 1))
            )
            json_scaler_modes.append({
                "width": video_mode["width"],
                "height": video_mode["height"],
                "aspect_w": aspect.numerator,
                "aspect_h": aspect.denominator,
                "rotation": video_mode.get("rotation", 0),
                "mirror": (video_mode.get("mirror_horizontal", False) << 1 | 
                           video_mode.get("mirror_vertical",   False) << 0)
            })
        return {
            "video": {
                "magic": "APF_VER_1",
                "scaler_modes": json_scaler_modes
            }
        }

    @property
    def audio_json(self):
        return {
            "audio": {
                "magic": "APF_VER_1" 
            }
        }

    @property
    def input_json(self):
        return {
            "input": {
                "magic": "APF_VER_1",
                "controllers": []
            }
        }
    
    @property
    def interact_json(self):
        return {
            "interact": {
                "magic": "APF_VER_1",
                "variables": [],
                "messages": []
            }
        }
    
    @property
    def data_json(self):
        return {
            "data": {
                "magic": "APF_VER_1",
                "data_slots": []
            }
        }

    @property
    def zip_filename(self):
        return f"{self.author}.{self.name}_{self.version}_{self.release_date}.zip"


class Package:
    def __init__(self, metadata: Metadata, cores: dict[str, bytes]):
        self.metadata = metadata
        self.cores = cores

    def files(self):
        def dump_json(data):
            return json.dumps(data, indent=4).encode("ascii")

        for platform_id, platform_json in self.metadata.platform_jsons.items():
            yield f"Platforms/{platform_id}.json", dump_json(platform_json)

        core_dir = self.metadata.core_directory
        yield f"{core_dir}/core.json", dump_json(self.metadata.core_json)
        info_txt = self.metadata.info_txt
        if info_txt:
            yield f"{core_dir}/info.txt", info_txt.encode("ascii")
        yield f"{core_dir}/video.json", dump_json(self.metadata.video_json)
        yield f"{core_dir}/audio.json", dump_json(self.metadata.audio_json)
        yield f"{core_dir}/input.json", dump_json(self.metadata.input_json)
        yield f"{core_dir}/interact.json", dump_json(self.metadata.interact_json)
        yield f"{core_dir}/data.json", dump_json(self.metadata.data_json)
        yield f"{core_dir}/variants.json", dump_json(self.metadata.variants_json)
        for core_id, core_bytes in enumerate(self.cores.values()):
            core_bytes_reversed = bytes(int(b.__format__("08b")[::-1], 2) for b in core_bytes)
            yield f"{core_dir}/core_{core_id}.rbf_r", core_bytes_reversed

    def write_files(self, root: Path):
        for filename, data in self.files():
            full_filename = Path(root) / filename
            full_filename.parent.mkdir(parents=True, exist_ok=True)
            with open(full_filename, "wb") as file:
                file.write(data)

    def write_zip_file(self, root: Path):
        with zipfile.ZipFile(Path(root) / self.metadata.zip_filename, "w") as archive:
            for filename, data in self.files():
                archive.writestr(zipfile.ZipInfo(filename), data)
        