import arcpy
from pathlib import Path
from typing import Optional


class PrintGeotechMap:
    """
    Export a Map Series PDF for one mine site, filtered to Status='Active'.

    Required config keys:
        aprx_path   : str  - path to the APRX (abs or relative to workspacePath)
        output_dir  : str  - output folder (abs or relative)

    Optional config keys (defaults shown):
        layout_name : str  - layout name in the APRX          (default: "Geotechnical Hazard Map")
        index_field : str  - map series index field name       (default: "MineSite")
        status_field: str  - field used to filter active pages (default: "Status")
        active_value: str  - value that means active           (default: "Active")
    """

    # Fallback defaults — overridden by anything supplied in config
    _DEFAULTS = {
        "layout_name":  "Geotechnical Hazard Map",
        "index_field":  "MineSite",
        "status_field": "Status",
        "active_value": "Active",
    }

    def __init__(self, mineSite: str, config: dict, workspacePath: str, userId: str):
        self.mineSite      = mineSite
        self.config        = {**self._DEFAULTS, **config}   # config wins over defaults
        self.workspacePath = Path(workspacePath) if workspacePath else Path.cwd()
        self.userId        = userId

        self._aprx:         Optional[arcpy.mp.ArcGISProject] = None
        self._layout:       Optional[arcpy.mp.Layout]        = None
        self._ms:           Optional[arcpy.mp.MapSeries]     = None
        self._index_layer                                    = None

    # ------------------------------ Public API ------------------------------

    def initialize(self) -> None:
        """Open APRX, resolve layout + map series + index layer, ensure output dir exists."""
        aprx_path = self._abs(self.config["aprx_path"])
        out_dir   = self._abs(self.config["output_dir"])

        self._aprx = arcpy.mp.ArcGISProject(str(aprx_path))

        layouts = self._aprx.listLayouts(self.config["layout_name"])
        if not layouts:
            raise RuntimeError(f"Layout not found: {self.config['layout_name']}")

        self._layout = layouts[0]
        self._ms     = self._layout.mapSeries

        if not self._ms or not self._ms.enabled:
            raise RuntimeError("Map Series is not enabled on the layout.")

        self._index_layer = self._ms.indexLayer
        if not self._index_layer:
            raise RuntimeError("Map Series index layer is missing.")

        out_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> Path:
        """Update 'Printed By', apply site + status filter, export one PDF."""
        self._update_printed_by()

        self._index_layer.definitionQuery = self._where_for_site(self.mineSite)  # type: ignore[union-attr]

        out_pdf = self._abs(self.config["output_dir"]) / f"{self.mineSite}.pdf"
        self._ms.exportToPDF(str(out_pdf))  # type: ignore[union-attr]
        return out_pdf

    # ---------------------------- Internal helpers ----------------------------

    def _abs(self, p: str) -> Path:
        """Return an absolute path, resolving relative paths against workspacePath."""
        path = Path(p)
        return path if path.is_absolute() else (self.workspacePath / path)

    def _update_printed_by(self) -> None:
        """Set 'Printed By: <userId>' on any matching text element."""
        if not self.userId:
            return
        for el in self._layout.listElements("TEXT_ELEMENT"):  # type: ignore[union-attr]
            if isinstance(el.text, str) and "Printed By" in el.text:
                el.text = f"Printed By: {self.userId}"
                break

    def _where_for_site(self, site: str) -> str:
        """Build: <index_field> = '<site>' AND <status_field> = '<active_value>'."""
        f_site   = arcpy.AddFieldDelimiters(self._index_layer, self.config["index_field"])
        f_status = arcpy.AddFieldDelimiters(self._index_layer, self.config["status_field"])

        site_val   = str(site).replace("'", "''")
        active_val = self.config["active_value"].replace("'", "''")

        return f"{f_site} = '{site_val}' AND {f_status} = '{active_val}'"


# ------------------------------ Example usage ------------------------------
if __name__ == "__main__":
    config = {
        # --- required ---
        "aprx_path":    r"L:\GIS\Joe_Working\DataDrivenPageUpLift\ArcPro\Geotech\your_project.aprx",
        "output_dir":   r"C:\Projects\Geotech",

        # --- optional: override only what differs from the defaults ---
        "layout_name":  "Geotechnical Hazard Map",
        "index_field":  "MineSite",
        "status_field": "Status",
        "active_value": "Active",
    }

    workspace = r"."        # base for resolving relative paths
    user_id   = "takapn"    # Printed By
    mine_site = "SF"        # e.g. "SF" or "MAC"

    job = PrintGeotechMap(mine_site, config, workspace, user_id)
    job.initialize()
    out_path = job.run()
    print(f"Exported: {out_path}")
