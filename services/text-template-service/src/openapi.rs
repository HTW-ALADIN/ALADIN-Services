use utoipa::{
    openapi::{
        schema::{AdditionalProperties, Discriminator, Schema},
        RefOr,
    },
    Modify, OpenApi,
};

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
    modifiers(&StrictTemplateSourceObjects),
    tags((name = "rendering", description = "Text template rendering"))
)]
pub struct ApiDoc;

struct StrictTemplateSourceObjects;

impl Modify for StrictTemplateSourceObjects {
    fn modify(&self, openapi: &mut utoipa::openapi::OpenApi) {
        if let Some(RefOr::T(Schema::OneOf(template_source))) = openapi
            .components
            .as_mut()
            .and_then(|components| components.schemas.get_mut("TemplateSource"))
        {
            template_source.discriminator = Some(Discriminator::new("kind"));
            for variant in &mut template_source.items {
                tighten_template_source_variant(variant);
            }
        }
    }
}

fn tighten_template_source_variant(variant: &mut RefOr<Schema>) {
    if let RefOr::T(Schema::Object(object)) = variant {
        object.additional_properties = Some(Box::new(AdditionalProperties::FreeForm(false)));
        if let Some(RefOr::T(Schema::Object(templates))) = object.properties.get_mut("templates") {
            templates.min_properties = Some(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use utoipa::{
        openapi::{OpenApi as OpenApiDocument, Ref, RefOr},
        Modify,
    };

    use super::{tighten_template_source_variant, StrictTemplateSourceObjects};

    #[test]
    fn schema_modifier_handles_missing_and_referenced_variants() {
        StrictTemplateSourceObjects.modify(&mut OpenApiDocument::default());

        let mut referenced = RefOr::Ref(Ref::new("#/components/schemas/ReferencedTemplateSource"));
        tighten_template_source_variant(&mut referenced);
    }
}
