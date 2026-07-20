# METHODE 1

# from django.conf import settings
# from graphene_django.views import GraphQLView
# from graphql import GraphQLError
# from graphql.validation import ValidationRule
#
#
# class DisableIntrospection(ValidationRule):
#     def enter_field(self, node, *_args):
#         if node.name.value in ("__schema", "__type"):
#             self.report_error(
#                 GraphQLError("GraphQL introspection is disabled.", [node])
#             )
#
# JAMAIS APPELé
# class SecureGraphQLView(GraphQLView):
#     def get_validation_rules(self):
#         rules = super().get_validation_rules()
#
#         if not settings.DEBUG:
#             return rules + [DisableIntrospection]
#
#         return rules


# METHODE 2 (Marche pas si on alias les __schema & __types)
# import json


# from django.http import JsonResponse
# from graphene_django.views import GraphQLView


# class SecureGraphQLView(GraphQLView):
#     def dispatch(self, request, *args, **kwargs):
#         query = ""

#         if request.method == "GET":
#             query = request.GET.get("query", "") or ""

#         elif request.method == "POST":
#             try:
#                 raw_body = request.body.decode("utf-8") if request.body else ""
#                 if raw_body:
#                     payload = json.loads(raw_body)
#                     query = payload.get("query", "") or ""
#                 else:
#                     query = request.POST.get("query", "") or ""
#             except Exception:
#                 query = request.POST.get("query", "") or ""

#         if "__schema" in query or "__type" in query:
#             return JsonResponse(
#                 {
#                     "errors": [
#                         {
#                             "message": "GraphQL introspection is disabled."
#                         }
#                     ]
#                 },
#                 status=403,
#             )

#         return super().dispatch(request, *args, **kwargs)


# METHODE 3 : allow __typename (AppoloJS mechanism) & search on Aliases too
from django.conf import settings
from graphene_django.views import GraphQLView
from graphql.error import GraphQLError
from graphql.validation import ValidationRule


class DisableIntrospectionRule(ValidationRule):
    """
    Règle de validation AST. Bloque __schema et __type (laisse passer __typename)
    """

    def enter_field(self, node, *_args):
        if node.name.value in ("__schema", "__type"):
            self.context.report_error(GraphQLError(message="GraphQL introspection is disabled.", nodes=[node]))


class SecureGraphQLView(GraphQLView):
    def execute_graphql_request(self, request, data, query, variables, operation_name, show_graphiql):
        """
        On injecte la règle directement dans les arguments d'exécution de Graphene.
        """
        if not settings.DEBUG:
            current_rules = self.validation_rules or []
            if DisableIntrospectionRule not in current_rules:
                self.validation_rules = list(current_rules) + [DisableIntrospectionRule]

        return super().execute_graphql_request(request, data, query, variables, operation_name, show_graphiql)
