import requests

import requests
import xml.etree.ElementTree as ET

class SankhyaAPI:
    def __init__(self, base_url, usuario, senha):
        self.base_url = base_url.rstrip('/')
        self.usuario = usuario
        self.senha = senha
        self.session_id = None

    def autenticar(self):
        url = f"{self.base_url}/service.sbr?serviceName=MobileLoginSP.login"
        xml = f"""
        <serviceRequest serviceName="MobileLoginSP.login">
            <requestBody>
                <NOMUSU>{self.usuario}</NOMUSU>
                <INTERNO>{self.senha}</INTERNO>
            </requestBody>
        </serviceRequest>
        """
        headers = {'Content-Type': 'text/xml'}
        resp = requests.post(url, data=xml, headers=headers)
        resp.raise_for_status()

        # Parse do XML
        root = ET.fromstring(resp.text)
        jsessionid_elem = root.find(".//jsessionid")
        if jsessionid_elem is not None:
            self.session_id = jsessionid_elem.text
        else:
            raise Exception("Não foi possível obter jsessionid da resposta")
        
        return self.session_id

    def request(self, service_name, body_xml):
        if not self.session_id:
            self.autenticar()
        url = f"{self.base_url}/service.sbr?serviceName={service_name}"
        headers = {
            'Content-Type': 'text/xml',
            'Cookie': f'JSESSIONID={self.session_id}'
        }
        resp = requests.post(url, data=body_xml, headers=headers)
        resp.raise_for_status()
        return resp.text





def buscar_itens_nota(api, numero_nota):
    body = {
        "dataSet": {
            "rootEntity": "ItemNota",
            "includePresentationFields": "S",
            "fields": ["SEQITEM", "PRODUTO.CODPROD", "PRODUTO.DESCRPROD", "QTDNEG"],
            "criteria": [{"expression": f"NUNOTA = {numero_nota}"}]
        }
    }
    return api.request("CRUDServiceProvider.loadRecords", body)
