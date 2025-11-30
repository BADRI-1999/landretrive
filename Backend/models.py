from pydantic import BaseModel, Field, ConfigDict # type: ignore

class Property(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    district_id: int | None = None
    district_name: str | None = None
    mandal_id: int | None = None
    mandal_name: str | None = None
    village_id: int | None = None
    village_name: str | None = None
    survey_no: str | None = None
    khata_id: int | None = None
    khata_label: float | None = None
    pattadar_name: str | None = Field(None, alias="pattadar_name_en")
    father_or_husband_name: str | None = Field(None, alias="father_or_husband_name_en")
    ppb_number: str | None = None
    ekyc_status: str | None = None
    total_extent_ac_gts: float | None = None
    land_status: str | None = None
    land_type: str | None = None
    market_value_inr: int | None = None

class surveyProperty(BaseModel):
    district_id: int | None = None
    district_name: str | None = None
    mandal_id: int | None = None
    mandal_name: str | None = None
    village_id: int | None = None
    village_name: str | None = None
    survey_no: str | None = None

class SearchResponse(BaseModel):
    count: int
    results: list[Property]

class SurveyResponse(BaseModel):
    count: int
    results: list[surveyProperty]