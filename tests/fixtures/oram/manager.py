# Oram 11d4e858367db465a431c701d9035432742a5a7d selector excerpt.
# Copyright Zynthian contributors; GPL-3.0-or-later.
import logging
from zyngine import *
engine2class = {
    "SF": object,
    "MC": object,
}
class Chain:
    engine_info = None
    single_processor_engines = ()
    zyngines = {}
    @classmethod
    def get_engine_info(cls):
        eng_info = zynthian_lv2.get_engines()
        if eng_info == cls.engine_info:
            return cls.engine_info
        cls.engine_info = eng_info
        for key, info in cls.engine_info.items():
            try:
                info['ENGINE'] = engine2class[key[:2]]
            except KeyError:
                info['ENGINE'] = None
                info['ENABLED'] = False
        return cls.engine_info
    def start_engine(self, eng_code):
        if False:
            pass
        elif eng_code in ("SF", "PD"):
            return "multiple"
        return "single"

    def filtered_engines_by_cat(self, etype, all=False):
        """Get dictionary of engine info filtered by type and indexed by catagory
            etype: type of engine
            all: include "disabled" engine too
        """
        result = {}
        if etype in zynthian_lv2.engines_by_type:
            # Add categories in right order
            for eng_cat in zynthian_lv2.engine_categories[etype]:
                result[eng_cat] = {}
            # Add engines to each category
            for eng_code, info in zynthian_lv2.engines_by_type[etype].items():
                eng_cat = info["CAT"]
                if eng_cat in result:
                    hide_if_single_proc = eng_code not in self.single_processor_engines or eng_code not in self.zyngines
                    if (info["ENABLED"] or all) and hide_if_single_proc:
                        result[eng_cat][eng_code] = info
                else:
                    logging.error(
                        f"Engine '{eng_code}' has invalid category '{eng_cat}'!")
            # Remove empty categories
            for eng_cat in list(result.keys()):
                if not result[eng_cat]:
                    del result[eng_cat]
        return result
