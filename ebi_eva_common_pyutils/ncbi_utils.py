import re

import requests
from retry import retry

from ebi_eva_common_pyutils.logger import logging_config as log_cfg


logger = log_cfg.get_logger(__name__)

eutils_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
esearch_url = eutils_url + 'esearch.fcgi'
esummary_url = eutils_url + 'esummary.fcgi'
efetch_url = eutils_url + 'efetch.fcgi'
ensembl_url = 'http://rest.ensembl.org/info/assembly'


@retry(tries=3, delay=2, backoff=1.2, jitter=(1, 3))
def get_ncbi_assembly_dicts_from_term(term, api_key=None):
    """Function to return NCBI assembly objects in the form of a list of dictionaries based on a search term."""
    payload = {'db': 'Assembly', 'term': '"{}"'.format(term), 'retmode': 'JSON'}
    if api_key:
        payload['api_key'] = api_key
    req = requests.get(esearch_url, params=payload)
    req.raise_for_status()
    data = req.json()
    assembly_dicts = []
    if data:
        assembly_id_list = data.get('esearchresult').get('idlist')
        payload = {'db': 'Assembly', 'id': ','.join(assembly_id_list), 'retmode': 'JSON'}
        if api_key:
            payload['api_key'] = api_key
        req = requests.get(esummary_url, params=payload)
        req.raise_for_status()
        summary_list = req.json()
        for assembly_id in summary_list.get('result', {}).get('uids', []):
            assembly_dicts.append(summary_list.get('result').get(assembly_id))
    return assembly_dicts


@retry(tries=3, delay=2, backoff=1.2, jitter=(1, 3))
def get_ncbi_taxonomy_dicts_from_term(term, api_key=None):
    """Function to return NCBI taxonomy objects in the form of a list of dictionaries based on a search term."""
    payload = {'db': 'Taxonomy', 'term': '"{}"'.format(term), 'retmode': 'JSON'}
    if api_key:
        payload['api_key'] = api_key
    req = requests.get(esearch_url, params=payload)
    req.raise_for_status()
    data = req.json()
    taxonomy_dicts = []
    if data:
        taxonomy_dicts = get_ncbi_taxonomy_dicts_from_ids(data.get('esearchresult').get('idlist'))
    return taxonomy_dicts


@retry(tries=3, delay=2, backoff=1.2, jitter=(1, 3))
def get_ncbi_taxonomy_dicts_from_ids(taxonomy_ids, api_key=None):
    """Function to return NCBI taxonomy objects in the form of a list of dictionaries
    based on a list of taxonomy ids."""
    taxonomy_dicts = []
    payload = {'db': 'Taxonomy', 'id': ','.join(taxonomy_ids), 'retmode': 'JSON'}
    if api_key:
        payload['api_key'] = api_key
    req = requests.get(esummary_url, params=payload)
    req.raise_for_status()
    summary_list = req.json()
    for taxonomy_id in summary_list.get('result', {}).get('uids', []):
        taxonomy_dicts.append(summary_list.get('result').get(taxonomy_id))
    return taxonomy_dicts


def get_ncbi_assembly_name_from_term(term):
    assembl_dicts = get_ncbi_assembly_dicts_from_term(term)
    assembly_names = set([d.get('assemblyname') for d in assembl_dicts])
    if len(assembly_names) > 1:
        # Only keep the one that have the assembly accession as a synonymous and check again
        assembly_names = set([d.get('assemblyname') for d in assembl_dicts
                              if term in d['synonym'].values() or term == d['assemblyaccession']])
    if len(assembly_names) != 1:
        raise ValueError(f'Cannot resolve assembly name for assembly {term} in NCBI. '
                         f'Found {",".join([str(a) for a in assembly_names])}')
    return assembly_names.pop() if assembly_names else None


def retrieve_species_scientific_name_from_tax_id_ncbi(taxid):
    payload = {'db': 'Taxonomy', 'id': taxid}
    r = requests.get(efetch_url, params=payload)
    match = re.search('<Rank>(.+?)</Rank>', r.text, re.MULTILINE)
    rank = None
    if match:
        rank = match.group(1)
    if rank not in ['species', 'subspecies']:
        logger.warning('Taxonomy id %s does not point to a species', taxid)
    match = re.search('<ScientificName>(.+?)</ScientificName>', r.text, re.MULTILINE)
    if match:
        return match.group(1)
