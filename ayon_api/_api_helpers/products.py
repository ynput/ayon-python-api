from __future__ import annotations

import collections
import warnings
import typing
from typing import Optional, Iterable, Generator, Any

from ayon_api.utils import (
    prepare_list_filters,
    create_entity_id,
)
from ayon_api.graphql_queries import (
    products_graphql_query,
    product_types_query,
)

from .base import BaseServerAPI, _PLACEHOLDER

if typing.TYPE_CHECKING:
    from ayon_api.typing import ProductDict, ProductTypeDict


class ProductsAPI(BaseServerAPI):
    def get_rest_product(
        self, project_name: str, product_id: str
    ) -> Optional["ProductDict"]:
        return self.get_rest_entity_by_id(project_name, "product", product_id)

    def get_products(
        self,
        project_name: str,
        product_ids: Optional[Iterable[str]] = None,
        product_names: Optional[Iterable[str]]=None,
        folder_ids: Optional[Iterable[str]]=None,
        product_types: Optional[Iterable[str]]=None,
        product_name_regex: Optional[str] = None,
        product_path_regex: Optional[str] = None,
        names_by_folder_ids: Optional[dict[str, Iterable[str]]] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: Optional[bool] = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Generator["ProductDict", None, None]:
        """Query products from server.

        Todos:
            Separate 'name_by_folder_ids' filtering to separated method. It
                cannot be combined with some other filters.

        Args:
            project_name (str): Name of project.
            product_ids (Optional[Iterable[str]]): Task ids to filter.
            product_names (Optional[Iterable[str]]): Task names used for
                filtering.
            folder_ids (Optional[Iterable[str]]): Ids of task parents.
                Use 'None' if folder is direct child of project.
            product_types (Optional[Iterable[str]]): Product types used for
                filtering.
            product_name_regex (Optional[str]): Filter products by name regex.
            product_path_regex (Optional[str]): Filter products by path regex.
                Path starts with folder path and ends with product name.
            names_by_folder_ids (Optional[dict[str, Iterable[str]]]): Product
                name filtering by folder id.
            statuses (Optional[Iterable[str]]): Product statuses used
                for filtering.
            tags (Optional[Iterable[str]]): Product tags used
                for filtering.
            active (Optional[bool]): Filter active/inactive products.
                Both are returned if is set to None.
            fields (Optional[Iterable[str]]): Fields to be queried for
                folder. All possible folder fields are returned
                if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                products.

        Returns:
            Generator[ProductDict, None, None]: Queried product entities.

        """
        if not project_name:
            return

        # Prepare these filters before 'name_by_filter_ids' filter
        filter_product_names = None
        if product_names is not None:
            filter_product_names = set(product_names)
            if not filter_product_names:
                return

        filter_folder_ids = None
        if folder_ids is not None:
            filter_folder_ids = set(folder_ids)
            if not filter_folder_ids:
                return

        # This will disable 'folder_ids' and 'product_names' filters
        #   - maybe could be enhanced in future?
        if names_by_folder_ids is not None:
            filter_product_names = set()
            filter_folder_ids = set()

            for folder_id, names in names_by_folder_ids.items():
                if folder_id and names:
                    filter_folder_ids.add(folder_id)
                    filter_product_names |= set(names)

            if not filter_product_names or not filter_folder_ids:
                return

        # Convert fields and add minimum required fields
        if fields:
            fields = set(fields) | {"id"}
            self._prepare_fields("product", fields)
        else:
            fields = self.get_default_fields_for_type("product")

        if active is not None:
            fields.add("active")

        if own_attributes is not _PLACEHOLDER:
            warnings.warn(
                (
                    "'own_attributes' is not supported for products. The"
                    " argument will be removed from function signature in"
                    " future (apx. version 1.0.10 or 1.1.0)."
                ),
                DeprecationWarning
            )

        # Add 'name' and 'folderId' if 'names_by_folder_ids' filter is entered
        if names_by_folder_ids:
            fields.add("name")
            fields.add("folderId")

        # Prepare filters for query
        filters = {
            "projectName": project_name
        }

        if filter_folder_ids:
            filters["folderIds"] = list(filter_folder_ids)

        if filter_product_names:
            filters["productNames"] = list(filter_product_names)

        if not prepare_list_filters(
            filters,
            ("productIds", product_ids),
            ("productTypes", product_types),
            ("productStatuses", statuses),
            ("productTags", tags),
        ):
            return

        for filter_key, filter_value in (
            ("productNameRegex", product_name_regex),
            ("productPathRegex", product_path_regex),
        ):
            if filter_value:
                filters[filter_key] = filter_value

        query = products_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        parsed_data = query.query(self)

        products = parsed_data.get("project", {}).get("products", [])
        # Filter products by 'names_by_folder_ids'
        if names_by_folder_ids:
            products_by_folder_id = collections.defaultdict(list)
            for product in products:
                filtered_product = self._filter_product(
                    project_name, product, active
                )
                if filtered_product is not None:
                    folder_id = filtered_product["folderId"]
                    products_by_folder_id[folder_id].append(filtered_product)

            for folder_id, names in names_by_folder_ids.items():
                for folder_product in products_by_folder_id[folder_id]:
                    if folder_product["name"] in names:
                        yield folder_product

        else:
            for product in products:
                filtered_product = self._filter_product(
                    project_name, product, active
                )
                if filtered_product is not None:
                    yield filtered_product

    def get_product_by_id(
        self,
        project_name: str,
        product_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional["ProductDict"]:
        """Query product entity by id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            product_id (str): Product id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                products.

        Returns:
            Optional[ProductDict]: Product entity data or None
                if was not found.

        """
        products = self.get_products(
            project_name,
            product_ids=[product_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for product in products:
            return product
        return None

    def get_product_by_name(
        self,
        project_name: str,
        product_name: str,
        folder_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional["ProductDict"]:
        """Query product entity by name and folder id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            product_name (str): Product name.
            folder_id (str): Folder id (Folder is a parent of products).
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                products.

        Returns:
            Optional[ProductDict]: Product entity data or None
                if was not found.

        """
        products = self.get_products(
            project_name,
            product_names=[product_name],
            folder_ids=[folder_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for product in products:
            return product
        return None

    def get_product_types(
        self, fields: Optional[Iterable[str]] = None
    ) -> list["ProductTypeDict"]:
        """Types of products.

        This is server wide information. Product types have 'name', 'icon' and
            'color'.

        Args:
            fields (Optional[Iterable[str]]): Product types fields to query.

        Returns:
            list[ProductTypeDict]: Product types information.

        """
        if not fields:
            fields = self.get_default_fields_for_type("productType")

        query = product_types_query(fields)

        parsed_data = query.query(self)

        return parsed_data.get("productTypes", [])

    def get_project_product_types(
        self, project_name: str, fields: Optional[Iterable[str]] = None
    ) -> list["ProductTypeDict"]:
        """DEPRECATED Types of products available in a project.

        Filter only product types available in a project.

        Args:
            project_name (str): Name of the project where to look for
                product types.
            fields (Optional[Iterable[str]]): Product types fields to query.

        Returns:
            list[ProductTypeDict]: Product types information.

        """
        warnings.warn(
            "Used deprecated function 'get_project_product_types'."
            " Use 'get_project' with 'productTypes' in 'fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if fields is None:
            fields = {"productTypes"}
        else:
            fields = {
                f"productTypes.{key}"
                for key in fields
            }

        project = self.get_project(project_name, fields=fields)
        return project["productTypes"]

    def get_product_type_names(
        self,
        project_name: Optional[str] = None,
        product_ids: Optional[Iterable[str]] = None,
    ) -> set[str]:
        """DEPRECATED Product type names.

        Warnings:
            This function will be probably removed. Matters if 'products_id'
                filter has real use-case.

        Args:
            project_name (Optional[str]): Name of project where to look for
                queried entities.
            product_ids (Optional[Iterable[str]]): Product ids filter. Can be
                used only with 'project_name'.

        Returns:
            set[str]: Product type names.

        """
        warnings.warn(
            "Used deprecated function 'get_product_type_names'."
            " Use 'get_product_types' or 'get_products' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if project_name:
            if not product_ids:
                return set()
            products = self.get_products(
                project_name,
                product_ids=product_ids,
                fields=["productType"],
                active=None,
            )
            return {
                product["productType"]
                for product in products
            }

        return {
            product_info["name"]
            for product_info in self.get_product_types(project_name)
        }

    def create_product(
        self,
        project_name: str,
        name: str,
        product_type: str,
        folder_id: str,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[Iterable[str]] =None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        product_id: Optional[str] = None,
    ) -> str:
        """Create new product.

        Args:
            project_name (str): Project name.
            name (str): Product name.
            product_type (str): Product type.
            folder_id (str): Parent folder id.
            attrib (Optional[dict[str, Any]]): Product attributes.
            data (Optional[dict[str, Any]]): Product data.
            tags (Optional[Iterable[str]]): Product tags.
            status (Optional[str]): Product status.
            active (Optional[bool]): Product active state.
            product_id (Optional[str]): Product id. If not passed new id is
                generated.

        Returns:
            str: Product id.

        """
        if not product_id:
            product_id = create_entity_id()
        create_data = {
            "id": product_id,
            "name": name,
            "productType": product_type,
            "folderId": folder_id,
        }
        for key, value in (
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                create_data[key] = value

        response = self.post(
            f"projects/{project_name}/products",
            **create_data
        )
        response.raise_for_status()
        return product_id

    def update_product(
        self,
        project_name: str,
        product_id: str,
        name: Optional[str] = None,
        folder_id: Optional[str] = None,
        product_type: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ):
        """Update product entity on server.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            product_id (str): Product id.
            name (Optional[str]): New product name.
            folder_id (Optional[str]): New product id.
            product_type (Optional[str]): New product type.
            attrib (Optional[dict[str, Any]]): New product attributes.
            data (Optional[dict[str, Any]]): New product data.
            tags (Optional[Iterable[str]]): New product tags.
            status (Optional[str]): New product status.
            active (Optional[bool]): New product active state.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("productType", product_type),
            ("folderId", folder_id),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                update_data[key] = value

        response = self.patch(
            f"projects/{project_name}/products/{product_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_product(self, project_name: str, product_id: str):
        """Delete product.

        Args:
            project_name (str): Project name.
            product_id (str): Product id to delete.

        """
        response = self.delete(
            f"projects/{project_name}/products/{product_id}"
        )
        response.raise_for_status()

    def _filter_product(
        self,
        project_name: str,
        product: "ProductDict",
        active: Optional[bool],
    ) -> Optional["ProductDict"]:
        if active is not None and product["active"] is not active:
            return None

        self._convert_entity_data(product)

        return product
