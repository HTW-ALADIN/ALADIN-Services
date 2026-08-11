use utoipa::OpenApi;

use crate::{
    api,
    error::ProblemDetails,
    model::{
        Autoescape, CapabilitiesResponse, EngineInfo, FeatureInfo, HealthResponse, LimitInfo,
        RenderMetadata, RenderOptions, RenderRequest, RenderResponse, TemplateSource,
        UndefinedBehavior,
    },
};

#[derive(OpenApi)]
#[openapi(
    info(
        title = "Text Template Service",
        version = "0.1.0",
        description = "Stateless MiniJinja text rendering through a REST and CLI contract"
    ),
    paths(api::health, api::capabilities, api::render_template),
    components(schemas(
        Autoescape,
        CapabilitiesResponse,
        EngineInfo,
        FeatureInfo,
        HealthResponse,
        LimitInfo,
        ProblemDetails,
        RenderMetadata,
        RenderOptions,
        RenderRequest,
        RenderResponse,
        TemplateSource,
        UndefinedBehavior
    )),
    tags((name = "rendering", description = "Text template rendering"))
)]
pub struct ApiDoc;
