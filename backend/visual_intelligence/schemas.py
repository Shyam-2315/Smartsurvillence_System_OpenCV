from pydantic import BaseModel, Field, model_validator

class EnhanceRequest(BaseModel):
    auto_contrast: bool = True
    clahe: bool = False
    denoise: bool = False
    sharpen: float = Field(default=0, ge=0, le=2)
    brightness: int = Field(default=0, ge=-100, le=100)
    contrast: float = Field(default=1, ge=.25, le=3)
    gamma: float = Field(default=1, ge=.2, le=3)
    grayscale: bool = False
    upscale: int = Field(default=1, ge=1, le=4)
    deskew: bool = False

class RegionRequest(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def stays_inside_image(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Region must stay within normalized image bounds")
        return self

class WebSearchRequest(BaseModel):
    selected_text: str | None = Field(default=None, min_length=3, max_length=160)
